# backend/scraper/facebook.py
import asyncio
import re
import random
from datetime import datetime, timezone, timedelta
from playwright.async_api import BrowserContext, Page

# Regex to extract Indian phone numbers from post text
_PHONE_RE = re.compile(r'(?:\+?91[\s\-]?)?[6-9]\d{9}')

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

    Uses in-browser JavaScript evaluation to find post containers reliably,
    since Facebook's React DOM doesn't consistently use [role='article'] for posts.
    """
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

    _dbg(f"=== scrape_group_for_area: group={group_url} area={area!r} ===")

    try:
        encoded_area = area.replace(" ", "%20") if area else ""
        search_url = (
            f"{FB}/groups/{group_id}/search?q={encoded_area}&filters={_RECENT_POSTS_FILTER}"
            if area else group_url
        )

        _dbg(f"Navigating to: {search_url}")
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as nav_e:
            _dbg(f"goto raised (continuing): {nav_e}")
        _dbg(f"URL after goto: {page.url}")
        await _human_delay(3, 5)

        # Click Recent posts toggle if not already checked
        try:
            toggle = await page.query_selector(
                "[aria-label='Recent posts'], label:has-text('Recent posts')"
            )
            if toggle:
                checked = await toggle.get_attribute("aria-checked")
                _dbg(f"Toggle found, aria-checked={checked!r}")
                if checked != "true":
                    await toggle.click()
                    _dbg("Toggle clicked — waiting for feed to refresh")
                    await _human_delay(4, 6)
            else:
                _dbg("No toggle found")
        except Exception as te:
            _dbg(f"Toggle error: {te}")

        # Quick empty-page check
        try:
            page_text = await page.inner_text("body")
            _dbg(f"Body preview: {page_text[:200]!r}")
            empty_phrases = ["no results", "no posts", "nothing matches", "0 results", "couldn't find anything"]
            if any(p in page_text.lower() for p in empty_phrases):
                _dbg("Empty page — returning []")
                _slog.close()
                return []
        except Exception as pe:
            _dbg(f"Body text error: {pe}")

        # Get group name once
        group_name = None
        try:
            h1 = await page.query_selector("h1")
            if h1:
                group_name = (await h1.inner_text()).strip() or None
        except Exception:
            pass

        # ── Main scroll + extract loop ──────────────────────────────────────
        for scroll_pass in range(8):
            if len(posts) >= max_posts:
                _dbg(f"Reached max_posts ({max_posts}), stopping")
                break

            _dbg(f"--- Scroll pass {scroll_pass + 1}/8 (posts: {len(posts)}) ---")
            await _slow_scroll(page, steps=4)
            await _human_delay(1.5, 3)

            # Expand all "See more" links via JS (works regardless of role/selector)
            try:
                expanded = await page.evaluate("""
                    () => {
                        let count = 0;
                        for (const el of document.querySelectorAll('div,span,a')) {
                            const txt = el.childNodes.length === 1
                                ? (el.textContent || '').trim()
                                : '';
                            if ((txt === 'See more' || txt === 'See More') &&
                                    el.offsetParent !== null) {
                                el.click();
                                count++;
                            }
                        }
                        return count;
                    }
                """)
                if expanded:
                    _dbg(f"  Clicked {expanded} 'See more' elements")
                    await asyncio.sleep(1)
            except Exception as sme:
                _dbg(f"  See more error: {sme}")

            # ── Extract posts via JavaScript ─────────────────────────────────
            # Strategy: find all timestamp elements on the page, walk up the DOM
            # to the post container (the ancestor that has Like + Comment buttons),
            # then pull out all required data in one JS call.
            try:
                js_posts = await page.evaluate("""
                    () => {
                        const results = [];
                        const seen = new Set();

                        const timeEls = document.querySelectorAll('abbr[data-utime], time[datetime]');

                        for (const timeEl of timeEls) {
                            // Walk up DOM to find the post container.
                            // A post container always has both a Like button and a Comment button.
                            let container = timeEl;
                            let foundContainer = false;
                            for (let i = 0; i < 30; i++) {
                                if (!container.parentElement) break;
                                container = container.parentElement;
                                const labels = Array.from(
                                    container.querySelectorAll('[aria-label]')
                                ).map(b => (b.getAttribute('aria-label') || '').toLowerCase());
                                if (labels.some(l => l.startsWith('like')) &&
                                        labels.some(l => l === 'comment')) {
                                    foundContainer = true;
                                    break;
                                }
                            }
                            if (!foundContainer) continue;

                            // ── Post URL ────────────────────────────────────
                            // Walk up from the timestamp element to find its anchor href
                            let postUrl = null;
                            let el = timeEl;
                            for (let i = 0; i < 10; i++) {
                                if (el.tagName === 'A' && el.href &&
                                        el.href.includes('/groups/')) {
                                    postUrl = el.href.split('?')[0];
                                    break;
                                }
                                if (!el.parentElement) break;
                                el = el.parentElement;
                            }
                            // Fallback: any /posts/ or /permalink/ link in the container
                            if (!postUrl) {
                                for (const a of container.querySelectorAll('a[href]')) {
                                    if (a.href.includes('/posts/') ||
                                            a.href.includes('/permalink/')) {
                                        postUrl = a.href.split('?')[0];
                                        break;
                                    }
                                }
                            }
                            if (!postUrl || seen.has(postUrl)) continue;
                            seen.add(postUrl);

                            // ── Timestamp ───────────────────────────────────
                            const tsUnix = timeEl.getAttribute('data-utime');
                            const tsDt   = timeEl.getAttribute('datetime');

                            // ── Poster name ─────────────────────────────────
                            const nameEl = container.querySelector(
                                'h2 a, h3 a, strong a, [data-testid="actor-name"] a'
                            );
                            const posterName = nameEl
                                ? nameEl.textContent.trim()
                                : null;

                            // ── Post text ────────────────────────────────────
                            let rawText = '';
                            const textEl = container.querySelector(
                                '[data-ad-comet-preview="message"], ' +
                                '[data-testid="post_message"], ' +
                                '[dir="auto"]'
                            );
                            if (textEl) rawText = textEl.innerText.trim();

                            // ── Images ───────────────────────────────────────
                            const imgs = Array.from(container.querySelectorAll('img[src]'))
                                .map(img => img.src)
                                .filter(src =>
                                    src.includes('scontent') && !src.includes('emoji'));

                            results.push({
                                post_url:        postUrl,
                                poster_name:     posterName,
                                timestamp_unix:  tsUnix,
                                timestamp_dt:    tsDt,
                                raw_text:        rawText,
                                image_urls:      imgs,
                            });
                        }

                        return results;
                    }
                """)

                _dbg(f"  JS found {len(js_posts)} candidate posts on page")

                for jp in js_posts:
                    url = jp.get("post_url", "")
                    if not url or url in seen_urls:
                        continue

                    # Skip posts with no images
                    if not jp.get("image_urls"):
                        _dbg(f"  Skip (no images): {url[:70]}")
                        continue

                    # Parse timestamp
                    posted_at = None
                    if jp.get("timestamp_unix"):
                        try:
                            posted_at = datetime.fromtimestamp(
                                int(jp["timestamp_unix"]), tz=timezone.utc
                            )
                        except (ValueError, TypeError):
                            pass
                    if not posted_at and jp.get("timestamp_dt"):
                        try:
                            posted_at = datetime.fromisoformat(
                                jp["timestamp_dt"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            pass

                    if posted_at and posted_at < cutoff:
                        _dbg(f"  Skip (too old, {posted_at}): {url[:60]}")
                        continue

                    # Extract phone numbers from post text
                    raw_text = jp.get("raw_text", "")
                    phones = list(set(_PHONE_RE.findall(raw_text)))

                    seen_urls.add(url)
                    posts.append({
                        "fb_post_url":   url,
                        "poster_name":   jp.get("poster_name"),
                        "posted_at":     posted_at,
                        "raw_text":      raw_text,
                        "phone_numbers": phones,
                        "image_urls":    jp.get("image_urls", []),
                        "group_name":    group_name,
                    })
                    _dbg(
                        f"  ACCEPTED: {url[:70]} "
                        f"imgs={len(jp.get('image_urls', []))} "
                        f"phones={phones}"
                    )

                    if len(posts) >= max_posts:
                        break

            except Exception as je:
                _dbg(f"  JS evaluation error: {je}")

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
