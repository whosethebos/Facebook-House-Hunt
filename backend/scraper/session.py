from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import BrowserContext
from config import settings


def _session_path() -> Path:
    return Path(settings.session_path)


def _session_is_valid() -> bool:
    """Return True if session file exists and is younger than SESSION_MAX_AGE_DAYS."""
    path = _session_path()
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - mtime
    return age < timedelta(days=settings.session_max_age_days)


async def save_session(context: BrowserContext) -> None:
    """Save Playwright storage state to disk."""
    path = _session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(path))


async def load_session_into_context(playwright) -> BrowserContext | None:
    """
    Return a BrowserContext loaded with the saved session, or None if no valid session.
    Caller is responsible for closing the browser.
    """
    if not _session_is_valid():
        return None
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = await browser.new_context(
        storage_state=str(_session_path()),
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    return context


async def login_and_save(playwright) -> BrowserContext:
    """
    Log into Facebook with credentials from settings, save session, return context.
    Raises ValueError if credentials are not configured.
    """
    if not settings.fb_email or not settings.fb_password:
        raise ValueError("FB_EMAIL and FB_PASSWORD must be set in .env")

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    await page.goto("https://www.facebook.com/login", wait_until="networkidle")
    await page.fill("#email", settings.fb_email)
    await page.fill("#pass", settings.fb_password)
    await page.click("[name='login']")
    await page.wait_for_url("https://www.facebook.com/", timeout=15000)
    await save_session(context)
    return context


async def get_context(playwright) -> BrowserContext:
    """
    Return a logged-in BrowserContext.
    Loads saved session if valid, otherwise performs fresh login.
    """
    ctx = await load_session_into_context(playwright)
    if ctx is not None:
        return ctx
    return await login_and_save(playwright)


def invalidate_session() -> None:
    """Delete saved session to force re-login on next run."""
    path = _session_path()
    if path.exists():
        path.unlink()
