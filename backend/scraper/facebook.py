# backend/scraper/facebook.py
import asyncio
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import BrowserContext, Page


async def _human_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Random delay to mimic human browsing speed."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _slow_scroll(page: Page, steps: int = 5) -> None:
    """Scroll down gradually to mimic human scrolling."""
    for _ in range(steps):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def discover_groups(context: BrowserContext, city: str, max_groups: int = 8) -> list[str]:
    """
    Search Facebook for rental groups in the given city.
    Returns list of group URLs (up to max_groups).
    """
    page = await context.new_page()
    group_urls: list[str] = []
    queries = [
        f"flat flatmates {city}",
        f"flat rent {city}",
        f"room rent {city}",
    ]
    seen: set[str] = set()

    for query in queries:
        if len(group_urls) >= max_groups:
            break
        try:
            encoded = query.replace(" ", "+")
            await page.goto(
                f"https://www.facebook.com/search/groups/?q={encoded}",
                wait_until="networkidle",
                timeout=20000,
            )
            await _human_delay(2, 4)

            # Each group result has a link containing /groups/ in href
            links = await page.query_selector_all("a[href*='/groups/']")
            for link in links:
                href = await link.get_attribute("href")
                if href and "/groups/" in href and "search" not in href:
                    # Normalise to just the group path
                    clean = href.split("?")[0].rstrip("/")
                    if clean not in seen and len(group_urls) < max_groups:
                        seen.add(clean)
                        group_urls.append(clean)
        except Exception:
            continue
        await _human_delay(1, 3)

    await page.close()
    return group_urls


async def scrape_group_for_area(
    context: BrowserContext,
    group_url: str,
    area: str,
    days_back: int = 7,
) -> list[dict]:
    """
    Search inside a Facebook group for posts mentioning `area`,
    filter to last `days_back` days, extract post data.
    Returns list of raw post dicts.
    """
    page = await context.new_page()
    posts: list[dict] = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    try:
        await page.goto(group_url, wait_until="networkidle", timeout=20000)
        await _human_delay(2, 4)

        # Click the group search icon/button
        search_btn = await page.query_selector("[aria-label='Search this group']")
        if not search_btn:
            search_btn = await page.query_selector("[placeholder='Search this group']")
        if not search_btn:
            # Try navigating directly to group search URL
            group_id = group_url.rstrip("/").split("/")[-1]
            await page.goto(
                f"https://www.facebook.com/groups/{group_id}/search/?q={area}",
                wait_until="networkidle",
                timeout=20000,
            )
        else:
            await search_btn.click()
            await _human_delay(1, 2)
            search_input = await page.wait_for_selector("input[type='search']", timeout=5000)
            await search_input.fill(area)
            await search_input.press("Enter")
            await _human_delay(2, 3)

        # Scroll and collect posts
        for scroll_pass in range(6):  # scroll up to 6 times
            await _slow_scroll(page, steps=4)
            await _human_delay(1.5, 3)

            # Find post containers — Facebook uses role="article" for feed posts
            articles = await page.query_selector_all("[role='article']")
            for article in articles:
                try:
                    post = await _extract_post(page, article)
                    if post is None:
                        continue
                    # Skip posts older than cutoff
                    if post.get("posted_at") and post["posted_at"] < cutoff:
                        continue
                    # Quick pre-filter: skip posts with no images
                    if not post.get("image_urls"):
                        continue
                    posts.append(post)
                except Exception:
                    continue

            await _human_delay(2, 4)

    except Exception:
        pass
    finally:
        await page.close()

    # Deduplicate by URL within this batch
    seen: set[str] = set()
    unique = []
    for p in posts:
        url = p.get("fb_post_url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(p)
    return unique


async def _extract_post(page: Page, article) -> dict | None:
    """Extract data from a single post article element."""
    # Post permalink — look for a timestamp link inside the article
    permalink = None
    time_links = await article.query_selector_all("a[href*='/posts/'], a[href*='?story_fbid=']")
    for link in time_links:
        href = await link.get_attribute("href")
        if href:
            permalink = href.split("?")[0]
            break

    if not permalink:
        return None

    # Poster name — first strong/b element or aria-label on actor link
    poster_name = None
    actor = await article.query_selector("[data-testid='actor-name'] a, h2 a")
    if actor:
        poster_name = (await actor.inner_text()).strip() or None

    # Post text — find the main text container
    raw_text = ""
    text_container = await article.query_selector(
        "[data-ad-comet-preview='message'], [data-testid='post_message'], [dir='auto']"
    )
    if text_container:
        raw_text = (await text_container.inner_text()).strip()

    # Images — find all img tags inside the article with substantial src
    image_urls: list[str] = []
    imgs = await article.query_selector_all("img[src]")
    for img in imgs:
        src = await img.get_attribute("src")
        if src and "scontent" in src and "emoji" not in src:
            image_urls.append(src)

    # Post date — try to parse the timestamp from a <abbr> or time element
    posted_at = None
    time_el = await article.query_selector("abbr[data-utime], time[datetime]")
    if time_el:
        ts = await time_el.get_attribute("data-utime")
        if ts:
            try:
                posted_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        dt_str = await time_el.get_attribute("datetime")
        if not posted_at and dt_str:
            try:
                posted_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Group name — from page title or URL
    group_name = None
    title_el = await page.query_selector("h1")
    if title_el:
        group_name = (await title_el.inner_text()).strip() or None

    return {
        "fb_post_url": permalink,
        "poster_name": poster_name,
        "posted_at": posted_at,
        "raw_text": raw_text,
        "image_urls": image_urls,
        "group_name": group_name,
    }
