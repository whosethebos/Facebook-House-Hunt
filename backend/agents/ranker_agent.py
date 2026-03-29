# backend/agents/ranker_agent.py
import asyncio
from google.adk.agents import BaseAgent
from db import postgres_client as db


class RankerAgent(BaseAgent):
    """Loads stored listings sorted by score and emits them as SSE listing events."""

    def __init__(self):
        super().__init__(
            name="ranker_agent",
            description="Ranks and streams final listing results",
        )

    async def rank_and_stream(
        self,
        search_id: str,
        queue: asyncio.Queue,
    ) -> int:
        """
        Load all listings for this search ordered by score, re-stream them.
        Returns total count.
        """
        listings = await db.list_listings(search_id)
        for listing in listings:
            await queue.put({"event": "listing", "data": listing})
        return len(listings)
