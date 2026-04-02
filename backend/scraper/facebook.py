# backend/scraper/facebook.py
import asyncio
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import BrowserContext, Page

# URL-encoded filter value for "Recent posts" in Facebook group search.
# Decoded: {"recentlyPosted":"true"}  (copied from observed Facebook URL)
_RECENT_POSTS_FILTER = "eyJyZWNlbnRseVBvc3RlZDoidHJ1ZSJ9"

FB = "https://www.facebook.com"

# Paths that appear in /groups/ hrefs but are not actual group pages
_SKIP_PATHS = {"groups", "search", "members", "media", "events", "files", "about", "permalink"}


async def _human_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Random delay to mimic human browsing speed."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _slow_scroll(page: Page, steps: int = 5) -> None:
    """Scroll down gradually to mimic human scrolling."""
    for _ in range(steps):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def discover_groups(context: BrowserContext, city: str, max_groups: int = 15) -> list[str]:
    """
    Search Facebook for rental groups in the given city.

    Searches using the Groups filter (search/groups/) with the primary query
    "flat and flatmates {city}", then falls back to broader queries until
    max_groups unique group URLs are collected.

    Returns list of absolute group URLs (up to max_groups).
    """
    page = await context.new_page()
    group_urls: list[str] = []
    queries = [
        f"flat and flatmates {city}",
        f"flat rent {city}",
        f"room rent {city}",
    ]
    seen: set[str] = set()

    for query in queries:
        if len(group_urls) >= max_groups:
            break
        try:
            encoded = query.replace(" ", "%20")
            # search/groups/ already applies the Groups filter shown in the screenshots
            await page.goto(
                f"{FB}/search/groups/?q={encoded}",
                wait_until="networkidle",
                timeout=25000,
            )
            await _human_delay(2, 4)

            # DEBUG: capture what Facebook actually shows us
            try:
                import os
                debug_path = f"/tmp/fb_debug_{query[:20].replace(' ', '_')}.png"
                await page.screenshot(path=debug_path, full_page=False)
                print(f"[DEBUG] Screenshot saved: {debug_path}")
                print(f"[DEBUG] Current URL: {page.url}")
                page_text_preview = (await page.inner_text("body"))[:300]
                print(f"[DEBUG] Page text preview: {page_text_preview!r}")
            except Exception as dbg_e:
                print(f"[DEBUG] Screenshot failed: {dbg_e}")

            links = await page.query_selector_all("a[href*='/groups/']")
            for link in links:
                href = await link.get_attribute("href")
                if not href:
                    continue
                # Make absolute (Facebook often returns relative hrefs)
                if href.startswith("/"):
                    href = FB + href
                if "/groups/" not in href:
                    continue
                # Strip query params and trailing slash to get the canonical URL
                clean = href.split("?")[0].rstrip("/")
                # Drop utility paths that aren't actual group home pages
                last_segment = clean.split("/")[-1]
                if last_segment in _SKIP_PATHS:
                    continue
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
    max_posts: int = 15,
) -> list[dict]:
    """
    Search inside a Facebook group for posts mentioning `area` with the
    "Recent posts" filter enabled, returning up to max_posts posts that
    have at least one image.

    Stops scrolling as soon as max_posts qualifying posts are collected.
    Returns deduplicated list of raw post dicts.
    """
    page = await context.new_page()
    posts: list[dict] = []
    seen_urls: set[str] = set()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    group_id = group_url.rstrip("/").split("/")[-1]

    try:
        if area:
            encoded_area = area.replace(" ", "%20")
            search_url = (
                f"{FB}/groups/{group_id}/search"
                f"?q={encoded_area}&filters={_RECENT_POSTS_FILTER}"
            )
        else:
            search_url = group_url

        await page.goto(search_url, wait_until="networkidle", timeout=25000)
        await _human_delay(2, 4)

        # Belt-and-suspenders: click the Recent posts toggle if visible and unchecked
        try:
            toggle = await page.query_selector(
                "[aria-label='Recent posts'], "
                "label:has-text('Recent posts')"
            )
            if toggle:
                checked = await toggle.get_attribute("aria-checked")
                if checked != "true":
                    await toggle.click()
                    await _human_delay(1, 2)
        except Exception:
            pass

        # Detect empty-result pages immediately and bail out — no point scrolling
        try:
            page_text = await page.inner_text("body")
            no_results_phrases = [
                "no results", "no posts", "nothing matches",
                "0 results", "couldn't find anything",
            ]
            if any(p in page_text.lower() for p in no_results_phrases):
                return []
        except Exception:
            pass

        # Scroll up to 8 passes; stop early once we have max_posts qualifying posts
        for _ in range(8):
            if len(posts) >= max_posts:
                break

            await _slow_scroll(page, steps=4)
            await _human_delay(1.5, 3)

            # Expand "See more" to get full post text
            try:
                see_more = await page.query_selector_all(
                    "[role='article'] [role='button']:has-text('See more'), "
                    "[role='article'] span:has-text('See more')"
                )
                for btn in see_more[:20]:
                    try:
                        await btn.click()
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            articles = await page.query_selector_all("[role='article']")
            for article in articles:
                if len(posts) >= max_posts:
                    break
                try:
                    post = await _extract_post(page, article)
                    if post is None:
                        continue
                    if post.get("posted_at") and post["posted_at"] < cutoff:
                        continue
                    if not post.get("image_urls"):
                        continue
                    url = post.get("fb_post_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        posts.append(post)
                except Exception:
                    continue

            await _human_delay(2, 4)

    except Exception:
        pass
    finally:
        await page.close()

    return posts


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
