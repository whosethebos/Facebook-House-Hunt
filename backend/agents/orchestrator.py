# backend/agents/orchestrator.py
import asyncio
from collections.abc import AsyncGenerator
from google.adk.agents import BaseAgent
from playwright.async_api import async_playwright
from scraper.session import get_context, invalidate_session, save_session
from agents.group_discovery import GroupDiscoveryAgent
from agents.scraper_agent import ScraperAgent
from agents.analyst_agent import AnalystAgent
from agents.ranker_agent import RankerAgent
from db import postgres_client as db


class OrchestratorAgent(BaseAgent):
    """Coordinates the full house hunt pipeline."""

    def __init__(self, search_id: str, city: str, areas: list[str],
                 budget_max: int | None, property_type: str | None,
                 furnishing: str | None, preferences: str | None):
        super().__init__(name="orchestrator_agent", description="Coordinates the pipeline")
        self.search_id = search_id
        self.city = city
        self.areas = areas
        self.budget_max = budget_max
        self.property_type = property_type
        self.furnishing = furnishing
        self.preferences = preferences
        self._queue: asyncio.Queue = asyncio.Queue()
        self._done = False

        self.group_discovery = GroupDiscoveryAgent()
        self.scraper = ScraperAgent()
        self.analyst = AnalystAgent()
        self.ranker = RankerAgent()

    async def run(self, extend: bool = False, extend_offset: int = 0) -> None:
        """Run the full pipeline. Called as a background task."""
        try:
            async with async_playwright() as pw:
                # Get or create FB session
                try:
                    context = await get_context(pw)
                except Exception as e:
                    await self._queue.put({
                        "event": "error",
                        "data": {"message": f"Facebook login failed: {str(e)[:100]}"},
                    })
                    await db.update_search_status(self.search_id, "failed")
                    return

                try:
                    # Step 1: Discover groups
                    groups = await self.group_discovery.discover(
                        context, self.city, self._queue,
                        extend_offset=extend_offset, max_groups=8,
                    )
                    if not groups:
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": f"No Facebook groups found for {self.city}"},
                        })
                        await db.update_search_status(self.search_id, "failed")
                        return

                    # Step 2: Scrape posts
                    posts = await self.scraper.scrape(
                        context, groups, self.areas, self._queue
                    )

                    # Step 3: Analyse posts + store listings
                    stored = await self.analyst.analyse(
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

            # Step 5: Finalise — count high-match results from DB (no re-streaming)
            # Note: RankerAgent.rank_and_stream() is used only by the SSE reconnect path
            # (when a client connects after the search is already complete).
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
