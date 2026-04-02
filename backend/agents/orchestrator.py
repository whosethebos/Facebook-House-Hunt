# backend/agents/orchestrator.py
import asyncio
from collections.abc import AsyncGenerator
from pydantic import ConfigDict, PrivateAttr
from google.adk.agents import BaseAgent
from playwright.async_api import async_playwright
import asyncio
from scraper.session import get_context, invalidate_session, save_session
from agents.group_discovery import GroupDiscoveryAgent
from agents.scraper_agent import ScraperAgent
from agents.analyst_agent import AnalystAgent
from agents.ranker_agent import RankerAgent
from db import postgres_client as db


class OrchestratorAgent(BaseAgent):
    """Coordinates the full house hunt pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Declared as Pydantic fields so BaseAgent (Pydantic model) allows them
    search_id: str
    city: str
    areas: list[str]
    budget_max: int | None
    property_type: str | None
    furnishing: str | None
    preferences: str | None
    group_urls: list[str] = []

    # Private attributes — not part of the Pydantic schema
    _queue: asyncio.Queue = PrivateAttr()
    _done: bool = PrivateAttr(default=False)
    _login_confirm_event: asyncio.Event | None = PrivateAttr(default=None)
    _group_discovery: GroupDiscoveryAgent = PrivateAttr()
    _scraper: ScraperAgent = PrivateAttr()
    _analyst: AnalystAgent = PrivateAttr()
    _ranker: RankerAgent = PrivateAttr()

    def __init__(self, search_id: str, city: str, areas: list[str],
                 budget_max: int | None, property_type: str | None,
                 furnishing: str | None, preferences: str | None,
                 group_urls: list[str] | None = None,
                 login_confirm_event: asyncio.Event | None = None):
        super().__init__(
            name="orchestrator_agent",
            description="Coordinates the pipeline",
            search_id=search_id,
            city=city,
            areas=areas,
            budget_max=budget_max,
            property_type=property_type,
            furnishing=furnishing,
            preferences=preferences,
            group_urls=group_urls or [],
        )
        self._queue = asyncio.Queue()
        self._done = False
        self._login_confirm_event = login_confirm_event
        self._group_discovery = GroupDiscoveryAgent()
        self._scraper = ScraperAgent()
        self._analyst = AnalystAgent()
        self._ranker = RankerAgent()

    async def run(self, extend: bool = False, extend_offset: int = 0) -> None:
        """Run the full pipeline. Called as a background task."""
        try:
            async with async_playwright() as pw:
                # Always start with a fresh Facebook session to avoid stale cookie issues
                invalidate_session()
                await self._queue.put({
                    "event": "login_required",
                    "data": {
                        "message": "A browser window has opened for Facebook login. "
                                   "Complete any 2FA steps, then click \"Continue\" in the app.",
                    },
                })
                try:
                    context = await get_context(pw, confirm_event=self._login_confirm_event)
                except Exception as e:
                    await self._queue.put({
                        "event": "error",
                        "data": {"message": f"Facebook login failed: {str(e)[:100]}"},
                    })
                    await db.update_search_status(self.search_id, "failed")
                    return

                try:
                    # Step 1: Discover groups (or reuse stored ones for refresh)
                    if self.group_urls:
                        groups = self.group_urls
                        await self._queue.put({
                            "event": "status",
                            "data": {
                                "message": f"Using {len(groups)} previously discovered groups",
                                "status": "reusing_groups",
                            },
                        })
                        # extend_offset is not applicable when reusing stored groups
                    else:
                        groups = await self._group_discovery.discover(
                            context, self.city, self._queue,
                            extend_offset=extend_offset, max_groups=15,
                        )
                        if not groups:
                            await self._queue.put({
                                "event": "error",
                                "data": {"message": f"No Facebook groups found for {self.city}"},
                            })
                            await db.update_search_status(self.search_id, "failed")
                            return
                        await db.save_group_urls(self.search_id, groups)

                    # Step 2: Scrape posts
                    posts = await self._scraper.scrape(
                        context, groups, self.areas, self._queue
                    )

                    # Step 3: Analyse posts + store listings
                    await self._analyst.analyse(
                        posts=posts,
                        search_id=self.search_id,
                        city=self.city,
                        areas=self.areas,
                        budget_max=self.budget_max,
                        property_type=self.property_type,
                        furnishing=self.furnishing,
                        preferences=self.preferences,
                        queue=self._queue,
                    )

                    # Step 4: Update session (refresh cookies)
                    await save_session(context)

                except Exception as e:
                    # Handle mid-scrape FB session expiry
                    if "login" in str(e).lower() or "session" in str(e).lower():
                        invalidate_session()
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": "Facebook session expired. Re-login on next search."},
                        })
                    else:
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": f"Pipeline error: {str(e)[:100]}"},
                        })
                    await db.update_search_status(self.search_id, "failed")
                    return

            # Step 5: Finalise
            listings = await db.list_listings(self.search_id)
            total = len(listings)
            high_match = sum(1 for l in listings if (l.get("match_score") or 0) >= 75)

            await db.update_search_status(self.search_id, "completed")
            await self._queue.put({
                "event": "complete",
                "data": {"total": total, "high_match": high_match, "status": "completed"},
            })

        except Exception as e:
            await self._queue.put({
                "event": "error",
                "data": {"message": f"Unexpected error: {str(e)[:100]}"},
            })
            await db.update_search_status(self.search_id, "failed")
        finally:
            self._done = True

    async def event_stream(self) -> AsyncGenerator[dict, None]:
        """Yield events from the queue until pipeline is done."""
        while not self._done or not self._queue.empty():
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
