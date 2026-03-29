# backend/agents/group_discovery.py
import asyncio
from google.adk.agents import BaseAgent
from scraper.facebook import discover_groups


class GroupDiscoveryAgent(BaseAgent):
    """Finds Facebook group URLs for a given city."""

    def __init__(self):
        super().__init__(
            name="group_discovery_agent",
            description="Discovers Facebook rental groups for a given city",
        )

    async def discover(
        self,
        context,          # Playwright BrowserContext
        city: str,
        queue: asyncio.Queue,
        extend_offset: int = 0,
        max_groups: int = 8,
    ) -> list[str]:
        """
        Find group URLs and emit SSE status events.
        extend_offset: skip the first N groups (used by extend search).
        Returns list of group URLs.
        """
        await queue.put({
            "event": "status",
            "data": {"message": f"Searching for Facebook groups in {city}...", "status": "discovering"},
        })
        groups = await discover_groups(context, city, max_groups=max_groups + extend_offset)
        groups = groups[extend_offset:]  # skip already-searched groups
        await queue.put({
            "event": "status",
            "data": {"message": f"Found {len(groups)} groups to search", "status": "discovering"},
        })
        return groups
