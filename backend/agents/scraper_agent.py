# backend/agents/scraper_agent.py
import asyncio
from google.adk.agents import BaseAgent
from scraper.facebook import scrape_group_for_area


class ScraperAgent(BaseAgent):
    """Scrapes posts from Facebook groups for given areas."""

    def __init__(self):
        super().__init__(
            name="scraper_agent",
            description="Extracts recent rental posts from Facebook groups",
        )

    async def scrape(
        self,
        context,          # Playwright BrowserContext
        group_urls: list[str],
        areas: list[str],
        queue: asyncio.Queue,
        days_back: int = 7,
    ) -> list[dict]:
        """
        For each group × area, scrape posts and emit SSE status events.
        Returns deduplicated list of raw post dicts.
        """
        all_posts: list[dict] = []
        seen_urls: set[str] = set()

        search_areas = areas if areas else [""]  # if no area specified, scrape feed directly

        for group_url in group_urls:
            group_short = group_url.rstrip("/").split("/")[-1]
            for area in search_areas:
                label = f"{group_short}" + (f" / {area}" if area else "")
                await queue.put({
                    "event": "status",
                    "data": {"message": f"Scraping group: {label}...", "status": "scraping"},
                })
                try:
                    posts = await scrape_group_for_area(context, group_url, area, days_back)
                    new_posts = [p for p in posts if p["fb_post_url"] not in seen_urls]
                    for p in new_posts:
                        seen_urls.add(p["fb_post_url"])
                    all_posts.extend(new_posts)
                    await queue.put({
                        "event": "status",
                        "data": {
                            "message": f"Found {len(new_posts)} new posts in {label}",
                            "status": "scraping",
                        },
                    })
                except Exception as e:
                    await queue.put({
                        "event": "status",
                        "data": {"message": f"Skipped {label}: {str(e)[:80]}", "status": "scraping"},
                    })

        await queue.put({
            "event": "status",
            "data": {
                "message": f"Scraping complete. {len(all_posts)} unique posts collected.",
                "status": "analysing",
            },
        })
        return all_posts
