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

    import sys
    _log = open("/tmp/fb_discover_debug.log", "w", buffering=1)

    def _dbg(msg: str) -> None:
        print(f"[DEBUG] {msg}", flush=True)
        _log.write(f"[DEBUG] {msg}\n")
        _log.flush()

    _dbg("discover_groups called")

    for query in queries:
        if len(group_urls) >= max_groups:
            break
        try:
            encoded = query.replace(" ", "%20")
            url = f"{FB}/search/groups/?q={encoded}"
            _dbg(f"Navigating to: {url}")
            # domcontentloaded is more reliable than networkidle on Facebook
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_e:
                _dbg(f"goto raised (continuing anyway): {nav_e}")
            _dbg(f"Current URL after goto: {page.url}")
            await _human_delay(3, 5)

            # Wait up to 10s for at least one group card link to appear
            try:
                await page.wait_for_selector("a[href*='/groups/']", timeout=10000)
            except Exception:
                _dbg("Timed out waiting for group links — trying anyway")

            await page.screenshot(path=f"/tmp/fb_debug_{query[:15].replace(' ', '_')}.png")
            _dbg("Screenshot saved")

            links = await page.query_selector_all("a[href*='/groups/']")
            _dbg(f"Raw links found: {len(links)}")
            for link in links:
                href = await link.get_attribute("href")
                if not href:
                    continue
                _dbg(f"  href: {href[:120]}")
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
                    _dbg(f"  FILTERED (skip path '{last_segment}'): {clean}")
                    continue
                if clean not in seen and len(group_urls) < max_groups:
                    seen.add(clean)
                    group_urls.append(clean)
                    _dbg(f"  ACCEPTED: {clean}")
        except Exception as e:
            _dbg(f"Exception during query '{query}': {e}")
            continue
        await _human_delay(1, 3)

    _dbg(f"discover_groups returning {len(group_urls)} groups")
    _log.close()

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
    import sys

    _slog = open("/tmp/fb_scrape_debug.log", "a", buffering=1)

    def _dbg(msg: str) -> None:
        print(f"[SCRAPE] {msg}", flush=True)
        _slog.write(f"[SCRAPE] {msg}\n")
        _slog.flush()

    page = await context.new_page()
    posts: list[dict] = []
    seen_urls: set[str] = set()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    group_id = group_url.rstrip("/").split("/")[-1]

    _dbg(f"=== scrape_group_for_area called: group={group_url} area={area!r} ===")

    try:
        if area:
            encoded_area = area.replace(" ", "%20")
            search_url = (
                f"{FB}/groups/{group_id}/search"
                f"?q={encoded_area}&filters={_RECENT_POSTS_FILTER}"
            )
        else:
            search_url = group_url

        _dbg(f"Navigating to: {search_url}")
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as nav_e:
            _dbg(f"goto raised (continuing anyway): {nav_e}")
        _dbg(f"Current URL after goto: {page.url}")
        await _human_delay(2, 4)

        # Screenshot of what loaded
        await page.screenshot(path=f"/tmp/fb_scrape_{group_id[:20]}.png")
        _dbg("Screenshot saved")

        # Belt-and-suspenders: click the Recent posts toggle if visible and unchecked
        try:
            toggle = await page.query_selector(
                "[aria-label='Recent posts'], "
                "label:has-text('Recent posts')"
            )
            if toggle:
                _dbg("Found 'Recent posts' toggle")
                checked = await toggle.get_attribute("aria-checked")
                _dbg(f"  aria-checked = {checked!r}")
                if checked != "true":
                    await toggle.click()
                    _dbg("  Clicked toggle")
                    await _human_delay(1, 2)
                else:
                    _dbg("  Already checked, skipping click")
            else:
                _dbg("No 'Recent posts' toggle found on page")
        except Exception as te:
            _dbg(f"Toggle error: {te}")

        # Detect empty-result pages immediately and bail out
        try:
            page_text = await page.inner_text("body")
            _dbg(f"Page body preview: {page_text[:300]!r}")
            no_results_phrases = [
                "no results", "no posts", "nothing matches",
                "0 results", "couldn't find anything",
            ]
            matched = [p for p in no_results_phrases if p in page_text.lower()]
            if matched:
                _dbg(f"Empty-result page detected (matched: {matched}) — returning []")
                _slog.close()
                return []
        except Exception as pe:
            _dbg(f"Page text check error: {pe}")

        # Scroll up to 8 passes; stop early once we have max_posts qualifying posts
        for scroll_pass in range(8):
            if len(posts) >= max_posts:
                _dbg(f"Reached max_posts ({max_posts}), stopping scroll")
                break

            _dbg(f"--- Scroll pass {scroll_pass + 1}/8 (posts so far: {len(posts)}) ---")
            await _slow_scroll(page, steps=4)
            await _human_delay(1.5, 3)

            # Expand "See more" to get full post text
            try:
                see_more = await page.query_selector_all(
                    "[role='article'] [role='button']:has-text('See more'), "
                    "[role='article'] span:has-text('See more')"
                )
                _dbg(f"  'See more' buttons found: {len(see_more)}")
                for btn in see_more[:20]:
                    try:
                        await btn.click()
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
            except Exception as sme:
                _dbg(f"  See more error: {sme}")

            articles = await page.query_selector_all("[role='article']")
            _dbg(f"  Articles found: {len(articles)}")
            for i, article in enumerate(articles):
                if len(posts) >= max_posts:
                    break
                try:
                    post = await _extract_post(page, article)
                    if post is None:
                        _dbg(f"    Article {i}: _extract_post returned None (no permalink)")
                        continue
                    if post.get("posted_at") and post["posted_at"] < cutoff:
                        _dbg(f"    Article {i}: too old ({post['posted_at']}) — skipped")
                        continue
                    if not post.get("image_urls"):
                        _dbg(f"    Article {i}: no images — skipped (url={post.get('fb_post_url', '?')[:60]})")
                        continue
                    url = post.get("fb_post_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        posts.append(post)
                        _dbg(f"    Article {i}: ACCEPTED — {url[:60]} images={len(post['image_urls'])}")
                    elif url in seen_urls:
                        _dbg(f"    Article {i}: duplicate — skipped")
                except Exception as ae:
                    _dbg(f"    Article {i}: exception — {ae}")
                    continue

            await _human_delay(2, 4)

    except Exception as e:
        _dbg(f"OUTER EXCEPTION: {e}")
    finally:
        await page.close()

    _dbg(f"=== Returning {len(posts)} posts ===")
    _slog.close()
    return posts


async def _extract_post(page: Page, article) -> dict | None:
    """Extract data from a single post article element."""
    # DEBUG: dump all hrefs in the article to find the right permalink pattern
    _elog = open("/tmp/fb_extract_debug.log", "a", buffering=1)
    try:
        all_links = await article.query_selector_all("a[href]")
        article_text_preview = (await article.inner_text())[:120].replace("\n", " ")
        _elog.write(f"\n[EXTRACT] Article text: {article_text_preview!r}\n")
        _elog.write(f"[EXTRACT] Total <a href> in article: {len(all_links)}\n")
        for al in all_links[:30]:
            ah = await al.get_attribute("href")
            _elog.write(f"[EXTRACT]   href: {(ah or '')[:120]}\n")
        _elog.flush()
    except Exception as de:
        _elog.write(f"[EXTRACT] debug dump error: {de}\n")
    finally:
        _elog.close()

    # Post permalink — try all known Facebook group post URL patterns
    permalink = None
    time_links = await article.query_selector_all(
        "a[href*='/posts/'], "
        "a[href*='?story_fbid='], "
        "a[href*='/permalink/'], "
        "a[href*='story_fbid'], "
        "a[href*='fbid=']"
    )
    for link in time_links:
        href = await link.get_attribute("href")
        if href:
            permalink = href.split("?")[0]
            break

    # Fallback: any link that goes into this group
    if not permalink:
        group_links = await article.query_selector_all("a[href*='/groups/']")
        for link in group_links:
            href = await link.get_attribute("href")
            if href and "/groups/" in href and not any(
                s in href for s in ["/search", "/members", "/media", "/events", "/about"]
            ):
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
