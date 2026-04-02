# backend/db/postgres_client.py
from psycopg.types.json import Json
from db.pool import get_pool


def _row(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {k: str(v) if k in ("id", "search_id") else v for k, v in d.items()}


def _rows(rows: list[dict]) -> list[dict]:
    return [_row(r) for r in rows]


# --- Searches ---

async def create_search(
    city: str,
    areas: list[str],
    budget_max: int | None = None,
    property_type: str | None = None,
    furnishing: str | None = None,
    preferences: str | None = None,
    raw_description: str | None = None,
) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            """INSERT INTO searches
               (city, areas, budget_max, property_type, furnishing, preferences, raw_description, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'running') RETURNING *""",
            (city, areas, budget_max, property_type, furnishing, preferences, raw_description),
        )
        return _row(await cur.fetchone())


async def get_search(search_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT * FROM searches WHERE id = %s", (search_id,))
        return _row(await cur.fetchone())


async def list_searches() -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            """SELECT s.*,
               COUNT(l.id) AS listing_count,
               MAX(l.match_score) AS top_score
               FROM searches s
               LEFT JOIN listings l ON l.search_id = s.id
               GROUP BY s.id
               ORDER BY s.created_at DESC"""
        )
        return _rows(await cur.fetchall())


async def delete_search(search_id: str) -> bool:
    """Delete a search and its listings (cascade). Returns True if found."""
    async with get_pool().connection() as conn:
        cur = await conn.execute("DELETE FROM searches WHERE id = %s", (search_id,))
        return cur.rowcount > 0


async def update_search_status(search_id: str, status: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE searches SET status = %s WHERE id = %s", (status, search_id)
        )


# --- Listings ---

async def insert_listing(
    search_id: str,
    fb_post_url: str,
    group_name: str | None,
    poster_name: str | None,
    posted_at,
    raw_text: str | None,
    image_urls: list[str],
    extracted_rent: int | None,
    extracted_area: str | None,
    extracted_type: str | None,
    extracted_furnishing: str | None,
    summary: str | None,
    match_score: int | None,
    score_breakdown: dict | None,
) -> dict | None:
    """Insert a listing. Returns None (not raises) on duplicate URL for this search."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            """INSERT INTO listings
               (search_id, fb_post_url, group_name, poster_name, posted_at,
                raw_text, image_urls, extracted_rent, extracted_area, extracted_type,
                extracted_furnishing, summary, match_score, score_breakdown)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (search_id, fb_post_url) DO NOTHING
               RETURNING *""",
            (
                search_id, fb_post_url, group_name, poster_name, posted_at,
                raw_text, image_urls, extracted_rent, extracted_area, extracted_type,
                extracted_furnishing, summary, match_score,
                Json(score_breakdown) if score_breakdown else None,
            ),
        )
        row = await cur.fetchone()
        return _row(row) if row else None


async def list_listings(search_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM listings WHERE search_id = %s ORDER BY match_score DESC NULLS LAST",
            (search_id,),
        )
        return _rows(await cur.fetchall())


async def save_group_urls(search_id: str, urls: list[str]) -> None:
    """Overwrite the group_urls array on a search. Silent no-op if search_id not found."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE searches SET group_urls = %s WHERE id = %s",
            (urls, search_id),
        )


async def delete_unpinned_listings(search_id: str) -> None:
    """Delete all non-pinned listings for a search. Pinned listings are preserved."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "DELETE FROM listings WHERE search_id = %s AND is_pinned = FALSE",
            (search_id,),
        )


async def toggle_pin(listing_id: str) -> dict | None:
    """Flip is_pinned on a listing. Returns updated row, or None if listing_id not found."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "UPDATE listings SET is_pinned = NOT is_pinned WHERE id = %s RETURNING *",
            (listing_id,),
        )
        row = await cur.fetchone()
        return _row(row) if row else None


async def get_listing(listing_id: str) -> dict | None:
    """Fetch a single listing by id."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM listings WHERE id = %s",
            (listing_id,),
        )
        row = await cur.fetchone()
        return _row(row) if row else None


async def update_listing_analysis(
    listing_id: str,
    extracted_rent: int | None,
    extracted_area: str | None,
    extracted_type: str | None,
    extracted_furnishing: str | None,
    summary: str | None,
    match_score: int | None,
    score_breakdown: dict | None,
) -> dict | None:
    """Overwrite the Ollama analysis fields on a listing. Returns the updated row."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            """UPDATE listings
               SET extracted_rent = %s, extracted_area = %s, extracted_type = %s,
                   extracted_furnishing = %s, summary = %s,
                   match_score = %s, score_breakdown = %s
               WHERE id = %s
               RETURNING *""",
            (
                extracted_rent, extracted_area, extracted_type,
                extracted_furnishing, summary,
                match_score,
                Json(score_breakdown) if score_breakdown else None,
                listing_id,
            ),
        )
        row = await cur.fetchone()
        return _row(row) if row else None
