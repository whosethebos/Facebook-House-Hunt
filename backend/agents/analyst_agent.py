# backend/agents/analyst_agent.py
import asyncio
from google.adk.agents import BaseAgent
from llm.analyze import analyze_post
from db import postgres_client as db


class AnalystAgent(BaseAgent):
    """Scores each post with Ollama and stores qualifying listings in DB."""

    DISCARD_THRESHOLD = 40  # posts scoring below this are not stored

    def __init__(self):
        super().__init__(
            name="analyst_agent",
            description="Analyses posts with Ollama weighted scoring",
        )

    async def analyse(
        self,
        posts: list[dict],
        search_id: str,
        city: str,
        areas: list[str],
        budget_max: int | None,
        property_type: str | None,
        furnishing: str | None,
        preferences: str | None,
        queue: asyncio.Queue,
    ) -> int:
        """
        Score all posts, store qualifying ones in DB, emit SSE listing events.
        Returns count of stored listings.
        """
        stored = 0
        total = len(posts)
        await queue.put({
            "event": "status",
            "data": {"message": f"Analysing {total} posts with Ollama...", "status": "analysing"},
        })

        for i, post in enumerate(posts, 1):
            try:
                result = await analyze_post(
                    post_text=post.get("raw_text", ""),
                    city=city,
                    areas=areas,
                    budget_max=budget_max,
                    property_type=property_type,
                    furnishing=furnishing,
                    preferences=preferences,
                )

                if result["match_score"] < self.DISCARD_THRESHOLD:
                    continue

                listing = await db.insert_listing(
                    search_id=search_id,
                    fb_post_url=post["fb_post_url"],
                    group_name=post.get("group_name"),
                    poster_name=post.get("poster_name"),
                    posted_at=post.get("posted_at"),
                    raw_text=post.get("raw_text"),
                    image_urls=post.get("image_urls", []),
                    extracted_rent=result["extracted_rent"],
                    extracted_area=result["extracted_area"],
                    extracted_type=result["extracted_type"],
                    extracted_furnishing=result["extracted_furnishing"],
                    summary=result["summary"],
                    match_score=result["match_score"],
                    score_breakdown=result["score_breakdown"],
                )

                if listing:
                    stored += 1
                    await queue.put({"event": "listing", "data": listing})

                if i % 5 == 0:
                    await queue.put({
                        "event": "status",
                        "data": {
                            "message": f"Analysed {i}/{total} posts, {stored} matches so far...",
                            "status": "analysing",
                        },
                    })
            except Exception:
                continue

        return stored
