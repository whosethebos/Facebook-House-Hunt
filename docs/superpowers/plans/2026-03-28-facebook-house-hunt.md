# Facebook House Hunt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack app that scrapes Facebook rental groups with Playwright, analyses posts with Ollama, and streams matching results live to a Next.js dashboard with search history.

**Architecture:** FastAPI backend with Google ADK agents (GroupDiscovery → Scraper → Analyst → Ranker) chained by an Orchestrator. SSE streams progress and results to the frontend. Playwright handles Facebook login with session persistence. PostgreSQL stores all searches and listings.

**Tech Stack:** Python 3.11+, FastAPI, psycopg[binary], psycopg-pool, google-adk, Playwright (async Chromium), httpx, Ollama, PostgreSQL 15+, Next.js 14 (App Router), Tailwind CSS, TypeScript

---

## File Map

### Backend
```
backend/
  main.py              FastAPI app — all endpoints + SSE streaming
  config.py            Pydantic Settings loaded from .env
  models.py            Pydantic request/response schemas
  pytest.ini           pytest config
  requirements.txt
  .env.example
  agents/
    __init__.py
    orchestrator.py    OrchestratorAgent — chains all sub-agents
    group_discovery.py GroupDiscoveryAgent — finds FB group URLs for a city
    scraper_agent.py   ScraperAgent — wraps facebook.py, emits SSE events
    analyst_agent.py   AnalystAgent — calls Ollama per post, stores listings
    ranker_agent.py    RankerAgent — sorts stored listings by score
  scraper/
    __init__.py
    session.py         Load/save Playwright storage state to fb_session.json
    facebook.py        Playwright: login, group search, post extraction
  llm/
    __init__.py
    ollama_client.py   Async httpx wrapper for Ollama /api/chat
    parse_criteria.py  NL text → ParsedCriteria dict via Ollama
    analyze.py         Post text + criteria → scored listing dict via Ollama
  db/
    __init__.py
    pool.py            psycopg AsyncConnectionPool open/close
    postgres_client.py CRUD for searches + listings tables
  session/
    .gitkeep           Directory for fb_session.json (gitignored)
  tests/
    __init__.py
    test_db.py         DB CRUD tests (requires local test DB)
    test_llm.py        LLM parse + analyze tests (mocked Ollama)
    test_api.py        FastAPI endpoint tests (mocked DB + agents)
```

### Frontend
```
frontend/
  app/
    layout.tsx         Root layout — dark theme, Inter font
    globals.css        Tailwind base styles
    page.tsx           Dashboard — past searches list + New Search button
    search/
      new/page.tsx     New search — NL input → auto-parsed fields → start
      [id]/page.tsx    Results — sidebar filters + live streaming listings
  components/
    SearchHistoryCard.tsx   Past search card on dashboard
    SearchInput.tsx         NL textarea + auto-parsed field chips
    ListingCard.tsx         Single listing card with score badge + FB link
    AgentStatusPanel.tsx    Live agent status panel (SSE status events)
  lib/
    api.ts             Typed fetch wrappers for all backend endpoints
    sse.ts             useSSE React hook for consuming SSE streams
  next.config.ts
  tailwind.config.ts
  tsconfig.json
  package.json
```

---

## Task 1: Backend Scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/pytest.ini`
- Create: `backend/session/.gitkeep`
- Create: `backend/agents/__init__.py`
- Create: `backend/scraper/__init__.py`
- Create: `backend/llm/__init__.py`
- Create: `backend/db/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create backend directory structure**

```bash
cd /path/to/Facebook-House-Hunt
mkdir -p backend/{agents,scraper,llm,db,session,tests}
touch backend/agents/__init__.py backend/scraper/__init__.py backend/llm/__init__.py backend/db/__init__.py backend/tests/__init__.py backend/session/.gitkeep
```

- [ ] **Step 2: Write requirements.txt**

```
# backend/requirements.txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
playwright>=1.50.0
httpx>=0.27.0
psycopg[binary]>=3.1
psycopg-pool>=3.2
pydantic>=2.9.0
pydantic-settings>=2.4.0
python-dotenv>=1.0.1
google-adk>=0.4.0
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 3: Write .env.example**

```
# backend/.env.example
FB_EMAIL=your@email.com
FB_PASSWORD=yourpassword
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
DATABASE_URL=postgresql://localhost:5432/facebook_house_hunt
FRONTEND_URL=http://localhost:3000
SESSION_PATH=session/fb_session.json
SESSION_MAX_AGE_DAYS=7
```

- [ ] **Step 4: Write pytest.ini**

```ini
# backend/pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 5: Install dependencies**

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

Expected: all packages install without error.

- [ ] **Step 6: Create the PostgreSQL database**

```bash
createdb facebook_house_hunt
```

Expected: database created (no output).

- [ ] **Step 7: Copy .env.example to .env and fill in your values**

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your FB credentials and DB URL
```

- [ ] **Step 8: Add session file to .gitignore**

Append to root `.gitignore` (create if missing):
```
backend/session/fb_session.json
backend/.env
```

- [ ] **Step 9: Commit scaffold**

```bash
git add backend/
git commit -m "feat: backend project scaffold and dependencies"
```

---

## Task 2: Database Schema and Connection Pool

**Files:**
- Create: `backend/db/pool.py`
- Create: `backend/db/schema.sql`

- [ ] **Step 1: Write pool.py**

```python
# backend/db/pool.py
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from config import settings

_pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        settings.database_url,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call open_pool() first.")
    return _pool
```

- [ ] **Step 2: Write schema.sql**

```sql
-- backend/db/schema.sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city TEXT NOT NULL,
    areas TEXT[] NOT NULL DEFAULT '{}',
    budget_max INT,
    property_type TEXT,
    furnishing TEXT,
    preferences TEXT,
    raw_description TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    fb_post_url TEXT NOT NULL,
    group_name TEXT,
    poster_name TEXT,
    posted_at TIMESTAMPTZ,
    raw_text TEXT,
    image_urls TEXT[] NOT NULL DEFAULT '{}',
    extracted_rent INT,
    extracted_area TEXT,
    extracted_type TEXT,
    extracted_furnishing TEXT,
    summary TEXT,
    match_score INT,
    score_breakdown JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(search_id, fb_post_url)
);
```

- [ ] **Step 3: Apply schema to database**

```bash
psql facebook_house_hunt < backend/db/schema.sql
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/db/
git commit -m "feat: database schema and connection pool"
```

---

## Task 3: Config and Pydantic Models

**Files:**
- Create: `backend/config.py`
- Create: `backend/models.py`

- [ ] **Step 1: Write config.py**

```python
# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    fb_email: str = ""
    fb_password: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    database_url: str = "postgresql://localhost:5432/facebook_house_hunt"
    frontend_url: str = "http://localhost:3000"
    session_path: str = "session/fb_session.json"
    session_max_age_days: int = 7


settings = Settings()
```

- [ ] **Step 2: Write models.py**

```python
# backend/models.py
from pydantic import BaseModel
from typing import Any


class ParseCriteriaRequest(BaseModel):
    description: str


class ParsedCriteria(BaseModel):
    city: str = ""
    areas: list[str] = []
    budget_max: int | None = None
    property_type: str | None = None   # "1BHK", "2BHK", "shared", "full apartment"
    furnishing: str | None = None      # "furnished", "semi", "unfurnished", "any"
    preferences: str | None = None     # free text extras


class CreateSearchRequest(BaseModel):
    city: str
    areas: list[str] = []
    budget_max: int | None = None
    property_type: str | None = None
    furnishing: str | None = None
    preferences: str | None = None
    raw_description: str | None = None


class SearchResponse(BaseModel):
    id: str
    city: str
    areas: list[str]
    budget_max: int | None
    property_type: str | None
    furnishing: str | None
    preferences: str | None
    raw_description: str | None
    status: str
    created_at: Any
    listing_count: int = 0
    top_score: int | None = None


class ListingResponse(BaseModel):
    id: str
    search_id: str
    fb_post_url: str
    group_name: str | None
    poster_name: str | None
    posted_at: Any
    raw_text: str | None
    image_urls: list[str]
    extracted_rent: int | None
    extracted_area: str | None
    extracted_type: str | None
    extracted_furnishing: str | None
    summary: str | None
    match_score: int | None
    score_breakdown: dict | None
    created_at: Any


class SearchWithListings(BaseModel):
    search: SearchResponse
    listings: list[ListingResponse]
```

- [ ] **Step 3: Commit**

```bash
git add backend/config.py backend/models.py
git commit -m "feat: config settings and Pydantic models"
```

---

## Task 4: Database CRUD Client

**Files:**
- Create: `backend/db/postgres_client.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_db.py
import pytest
import asyncio
from db.pool import open_pool, close_pool
from db import postgres_client as db


@pytest.fixture(autouse=True)
async def pool():
    await open_pool()
    yield
    # Clean up test data
    from db.pool import get_pool
    async with get_pool().connection() as conn:
        await conn.execute("DELETE FROM searches WHERE city = 'TestCity'")
    await close_pool()


async def test_create_and_get_search():
    search = await db.create_search(
        city="TestCity",
        areas=["Area1", "Area2"],
        budget_max=20000,
        property_type="1BHK",
        furnishing="furnished",
        preferences="no brokerage",
        raw_description="test description",
    )
    assert search["id"] is not None
    assert search["city"] == "TestCity"
    assert search["areas"] == ["Area1", "Area2"]
    assert search["status"] == "running"

    fetched = await db.get_search(search["id"])
    assert fetched["city"] == "TestCity"


async def test_update_search_status():
    search = await db.create_search(city="TestCity", areas=[])
    await db.update_search_status(search["id"], "completed")
    updated = await db.get_search(search["id"])
    assert updated["status"] == "completed"


async def test_insert_and_list_listings():
    search = await db.create_search(city="TestCity", areas=["TestArea"])
    listing = await db.insert_listing(
        search_id=search["id"],
        fb_post_url="https://facebook.com/groups/123/posts/456",
        group_name="Test Group",
        poster_name="John",
        posted_at=None,
        raw_text="1BHK available in TestArea",
        image_urls=["https://example.com/img.jpg"],
        extracted_rent=15000,
        extracted_area="TestArea",
        extracted_type="1BHK",
        extracted_furnishing="furnished",
        summary="Nice 1BHK",
        match_score=85,
        score_breakdown={"area": 25, "budget": 22},
    )
    assert listing["match_score"] == 85

    listings = await db.list_listings(search["id"])
    assert len(listings) == 1
    assert listings[0]["fb_post_url"] == "https://facebook.com/groups/123/posts/456"


async def test_duplicate_listing_skipped():
    search = await db.create_search(city="TestCity", areas=[])
    url = "https://facebook.com/groups/1/posts/1"
    await db.insert_listing(
        search_id=search["id"], fb_post_url=url,
        group_name=None, poster_name=None, posted_at=None,
        raw_text="x", image_urls=[], extracted_rent=None,
        extracted_area=None, extracted_type=None, extracted_furnishing=None,
        summary=None, match_score=50, score_breakdown=None,
    )
    # Second insert with same URL should not raise, just skip
    result = await db.insert_listing(
        search_id=search["id"], fb_post_url=url,
        group_name=None, poster_name=None, posted_at=None,
        raw_text="x", image_urls=[], extracted_rent=None,
        extracted_area=None, extracted_type=None, extracted_furnishing=None,
        summary=None, match_score=50, score_breakdown=None,
    )
    assert result is None  # duplicate returns None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && pytest tests/test_db.py -v
```

Expected: FAIL — `postgres_client` has no `create_search` function.

- [ ] **Step 3: Write postgres_client.py**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && pytest tests/test_db.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/ backend/tests/test_db.py
git commit -m "feat: database CRUD client with tests"
```

---

## Task 5: Ollama Client

**Files:**
- Create: `backend/llm/ollama_client.py`

- [ ] **Step 1: Write ollama_client.py**

```python
# backend/llm/ollama_client.py
import json
import httpx
from config import settings


async def chat(messages: list[dict], response_format: str = "text") -> str:
    """
    Send a chat request to Ollama.
    messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
    response_format: "text" or "json"
    Returns the model's response content as a string.
    """
    payload: dict = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
    }
    if response_format == "json":
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


async def chat_json(messages: list[dict]) -> dict:
    """Like chat() but requests JSON output and parses the result."""
    content = await chat(messages, response_format="json")
    return json.loads(content)
```

- [ ] **Step 2: Commit**

```bash
git add backend/llm/ollama_client.py
git commit -m "feat: Ollama async HTTP client"
```

---

## Task 6: NL Criteria Parser

**Files:**
- Create: `backend/llm/parse_criteria.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch
from llm.parse_criteria import parse_criteria
from llm.analyze import analyze_post

# --- parse_criteria tests ---

async def test_parse_criteria_extracts_fields():
    mock_response = {
        "city": "Pune",
        "areas": ["Hinjewadi"],
        "budget_max": 15000,
        "property_type": "1BHK",
        "furnishing": "furnished",
        "preferences": "no brokerage",
    }
    with patch("llm.parse_criteria.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await parse_criteria("Looking for furnished 1BHK in Pune near Hinjewadi, budget 15k, no brokerage")
    assert result["city"] == "Pune"
    assert result["areas"] == ["Hinjewadi"]
    assert result["budget_max"] == 15000
    assert result["property_type"] == "1BHK"
    assert result["furnishing"] == "furnished"


async def test_parse_criteria_handles_missing_fields():
    mock_response = {"city": "Mumbai", "areas": [], "budget_max": None,
                     "property_type": None, "furnishing": None, "preferences": None}
    with patch("llm.parse_criteria.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await parse_criteria("Looking for a place in Mumbai")
    assert result["city"] == "Mumbai"
    assert result["areas"] == []
    assert result["budget_max"] is None


# --- analyze_post tests ---

async def test_analyze_post_returns_score():
    mock_response = {
        "extracted_rent": 14500,
        "extracted_area": "Hinjewadi Phase 2",
        "extracted_type": "1BHK",
        "extracted_furnishing": "furnished",
        "scores": {"area": 28, "budget": 24, "type": 18, "furnishing": 12, "preferences": 8},
        "total_score": 90,
        "summary": "Furnished 1BHK in Hinjewadi Phase 2",
    }
    with patch("llm.analyze.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await analyze_post(
            post_text="1BHK available in Hinjewadi Phase 2, fully furnished, ₹14,500/mo",
            city="Pune",
            areas=["Hinjewadi"],
            budget_max=15000,
            property_type="1BHK",
            furnishing="furnished",
            preferences="no brokerage",
        )
    assert result["match_score"] == 90
    assert result["extracted_rent"] == 14500
    assert result["score_breakdown"]["area"] == 28


async def test_analyze_post_returns_fallback_on_error():
    with patch("llm.analyze.chat_json", side_effect=Exception("Ollama unreachable")):
        result = await analyze_post(
            post_text="some post",
            city="Pune", areas=[], budget_max=None,
            property_type=None, furnishing=None, preferences=None,
        )
    assert result["match_score"] == 0
    assert result["summary"] == ""
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && pytest tests/test_llm.py -v
```

Expected: FAIL — `parse_criteria` module not found.

- [ ] **Step 3: Write parse_criteria.py**

```python
# backend/llm/parse_criteria.py
from llm.ollama_client import chat_json

_FALLBACK: dict = {
    "city": "",
    "areas": [],
    "budget_max": None,
    "property_type": None,
    "furnishing": None,
    "preferences": None,
}

_PROMPT = """You are extracting house hunting search criteria from a user's natural language description.

Return a JSON object with exactly these fields:
- city: string (city name, or empty string if not found)
- areas: array of strings (locality/neighbourhood names within the city)
- budget_max: integer (maximum monthly rent in rupees, or null)
- property_type: string — one of "1BHK", "2BHK", "3BHK", "shared", "full apartment", "studio", or null
- furnishing: string — one of "furnished", "semi-furnished", "unfurnished", "any", or null
- preferences: string (any other preferences like "no brokerage", "male only", "near metro", or null)

User description: {description}"""


async def parse_criteria(description: str) -> dict:
    """Extract structured search criteria from natural language. Returns fallback on error."""
    try:
        result = await chat_json([
            {"role": "user", "content": _PROMPT.format(description=description)}
        ])
        return {
            "city": result.get("city", "") or "",
            "areas": result.get("areas") or [],
            "budget_max": result.get("budget_max"),
            "property_type": result.get("property_type"),
            "furnishing": result.get("furnishing"),
            "preferences": result.get("preferences"),
        }
    except Exception:
        return {**_FALLBACK}
```

- [ ] **Step 4: Run tests to confirm parse_criteria tests pass**

```bash
cd backend && pytest tests/test_llm.py::test_parse_criteria_extracts_fields tests/test_llm.py::test_parse_criteria_handles_missing_fields -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/llm/parse_criteria.py backend/tests/test_llm.py
git commit -m "feat: NL criteria parser with Ollama"
```

---

## Task 7: Post Analyzer

**Files:**
- Create: `backend/llm/analyze.py`

- [ ] **Step 1: Write analyze.py**

```python
# backend/llm/analyze.py
from llm.ollama_client import chat_json

_FALLBACK: dict = {
    "extracted_rent": None,
    "extracted_area": None,
    "extracted_type": None,
    "extracted_furnishing": None,
    "match_score": 0,
    "score_breakdown": {},
    "summary": "",
}

_PROMPT = """You are analysing a Facebook house rental post to see how well it matches a user's criteria.

USER CRITERIA:
- City: {city}
- Preferred areas: {areas}
- Max budget: {budget_max}
- Property type: {property_type}
- Furnishing: {furnishing}
- Other preferences: {preferences}

FACEBOOK POST TEXT:
{post_text}

SCORING RULES (allocate points out of the maximum for each criterion):
- area match (max 30): 30 if post is in one of the preferred areas, 15 if nearby, 0 if different area
- budget match (max 25): 25 if rent <= budget_max, 15 if within 20% over, 0 if null budget_max (skip check)
- property type match (max 20): 20 if exact match, 10 if similar, 0 if mismatch or null
- furnishing match (max 15): 15 if exact match, 8 if partial, 0 if mismatch or null
- preferences match (max 10): 10 if all preferences met, 5 if partial, 0 if not met or null

Return a JSON object:
{{
  "extracted_rent": integer or null (monthly rent in INR parsed from post),
  "extracted_area": string or null (locality extracted from post),
  "extracted_type": string or null (e.g. "1BHK", "2BHK", "shared"),
  "extracted_furnishing": string or null (e.g. "furnished", "unfurnished"),
  "scores": {{
    "area": integer,
    "budget": integer,
    "type": integer,
    "furnishing": integer,
    "preferences": integer
  }},
  "total_score": integer (sum of scores above),
  "summary": string (one sentence summary of the listing)
}}"""


async def analyze_post(
    post_text: str,
    city: str,
    areas: list[str],
    budget_max: int | None,
    property_type: str | None,
    furnishing: str | None,
    preferences: str | None,
) -> dict:
    """Score a post against criteria. Returns fallback dict on error."""
    try:
        result = await chat_json([{
            "role": "user",
            "content": _PROMPT.format(
                city=city,
                areas=", ".join(areas) if areas else "any",
                budget_max=f"₹{budget_max}" if budget_max else "not specified",
                property_type=property_type or "any",
                furnishing=furnishing or "any",
                preferences=preferences or "none",
                post_text=post_text[:3000],  # cap to avoid token limits
            ),
        }])
        scores = result.get("scores", {})
        return {
            "extracted_rent": result.get("extracted_rent"),
            "extracted_area": result.get("extracted_area"),
            "extracted_type": result.get("extracted_type"),
            "extracted_furnishing": result.get("extracted_furnishing"),
            "match_score": int(result.get("total_score", 0)),
            "score_breakdown": scores,
            "summary": result.get("summary", ""),
        }
    except Exception:
        return {**_FALLBACK}
```

- [ ] **Step 2: Run remaining LLM tests**

```bash
cd backend && pytest tests/test_llm.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/llm/analyze.py
git commit -m "feat: post analyzer with weighted scoring via Ollama"
```

---

## Task 8: Facebook Session Management

**Files:**
- Create: `backend/scraper/session.py`

- [ ] **Step 1: Write session.py**

```python
# backend/scraper/session.py
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import BrowserContext, async_playwright
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/scraper/session.py
git commit -m "feat: Facebook session management with Playwright storage state"
```

---

## Task 9: Facebook Scraper

**Files:**
- Create: `backend/scraper/facebook.py`

> **Note:** This module uses Playwright to interact with Facebook's live UI. DOM selectors may need adjustment if Facebook updates its layout. Test manually with `headless=False` during development to observe behaviour.

- [ ] **Step 1: Write facebook.py**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/scraper/facebook.py
git commit -m "feat: Facebook Playwright scraper with anti-bot measures"
```

---

## Task 10: Google ADK Agents

**Files:**
- Create: `backend/agents/group_discovery.py`
- Create: `backend/agents/scraper_agent.py`
- Create: `backend/agents/analyst_agent.py`
- Create: `backend/agents/ranker_agent.py`

- [ ] **Step 1: Write group_discovery.py**

```python
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
```

- [ ] **Step 2: Write scraper_agent.py**

```python
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
```

- [ ] **Step 3: Write analyst_agent.py**

```python
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
```

- [ ] **Step 4: Write ranker_agent.py**

```python
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
```

- [ ] **Step 5: Commit**

```bash
git add backend/agents/
git commit -m "feat: Google ADK agents — GroupDiscovery, Scraper, Analyst, Ranker"
```

---

## Task 11: Orchestrator Agent

**Files:**
- Create: `backend/agents/orchestrator.py`

- [ ] **Step 1: Write orchestrator.py**

```python
# backend/agents/orchestrator.py
import asyncio
from collections.abc import AsyncGenerator
from google.adk.agents import BaseAgent
from playwright.async_api import async_playwright
from scraper.session import get_context, invalidate_session, save_session
from agents.group_discovery import GroupDiscoveryAgent
from agents.scraper_agent import ScraperAgent
from agents.analyst_agent import AnalystAgent
from agents.ranker_agent import RankerAgent
from db import postgres_client as db


class OrchestratorAgent(BaseAgent):
    """Coordinates the full house hunt pipeline."""

    def __init__(self, search_id: str, city: str, areas: list[str],
                 budget_max: int | None, property_type: str | None,
                 furnishing: str | None, preferences: str | None):
        super().__init__(name="orchestrator_agent", description="Coordinates the pipeline")
        self.search_id = search_id
        self.city = city
        self.areas = areas
        self.budget_max = budget_max
        self.property_type = property_type
        self.furnishing = furnishing
        self.preferences = preferences
        self._queue: asyncio.Queue = asyncio.Queue()
        self._done = False

        self.group_discovery = GroupDiscoveryAgent()
        self.scraper = ScraperAgent()
        self.analyst = AnalystAgent()
        self.ranker = RankerAgent()

    async def run(self, extend: bool = False, extend_offset: int = 0) -> None:
        """Run the full pipeline. Called as a background task."""
        try:
            async with async_playwright() as pw:
                # Get or create FB session
                try:
                    context = await get_context(pw)
                except Exception as e:
                    await self._queue.put({
                        "event": "error",
                        "data": {"message": f"Facebook login failed: {str(e)[:100]}"},
                    })
                    await db.update_search_status(self.search_id, "failed")
                    return

                try:
                    # Step 1: Discover groups
                    groups = await self.group_discovery.discover(
                        context, self.city, self._queue,
                        extend_offset=extend_offset, max_groups=8,
                    )
                    if not groups:
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": f"No Facebook groups found for {self.city}"},
                        })
                        await db.update_search_status(self.search_id, "failed")
                        return

                    # Step 2: Scrape posts
                    posts = await self.scraper.scrape(
                        context, groups, self.areas, self._queue
                    )

                    # Step 3: Analyse posts + store listings
                    stored = await self.analyst.analyse(
                        posts=posts,
                        search_id=self.search_id,
                        city=self.city,
                        areas=self.areas,
                        budget_max=self.budget_max,
                        property_type=self.property_type,
                        furnishing=self.furnishing,
                        preferences=self.preferences,
                        queue=self._queue,
                    )

                    # Step 4: Update session (refresh cookies)
                    await save_session(context)

                except Exception as e:
                    # Handle mid-scrape FB session expiry
                    if "login" in str(e).lower() or "session" in str(e).lower():
                        invalidate_session()
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": "Facebook session expired. Re-login on next search."},
                        })
                    else:
                        await self._queue.put({
                            "event": "error",
                            "data": {"message": f"Pipeline error: {str(e)[:100]}"},
                        })
                    await db.update_search_status(self.search_id, "failed")
                    return

            # Step 5: Finalise — count high-match results from DB (no re-streaming)
            # Note: RankerAgent.rank_and_stream() is used only by the SSE reconnect path
            # (when a client connects after the search is already complete).
            listings = await db.list_listings(self.search_id)
            total = len(listings)
            high_match = sum(1 for l in listings if (l.get("match_score") or 0) >= 75)

            await db.update_search_status(self.search_id, "completed")
            await self._queue.put({
                "event": "complete",
                "data": {"total": total, "high_match": high_match, "status": "completed"},
            })

        except Exception as e:
            await self._queue.put({
                "event": "error",
                "data": {"message": f"Unexpected error: {str(e)[:100]}"},
            })
            await db.update_search_status(self.search_id, "failed")
        finally:
            self._done = True

    async def event_stream(self) -> AsyncGenerator[dict, None]:
        """Yield events from the queue until pipeline is done."""
        while not self._done or not self._queue.empty():
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
```

- [ ] **Step 2: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat: OrchestratorAgent wiring full pipeline"
```

---

## Task 12: FastAPI Application

**Files:**
- Create: `backend/main.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing API test**

```python
# backend/tests/test_api.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_parse_criteria():
    mock_result = {
        "city": "Pune", "areas": ["Hinjewadi"], "budget_max": 15000,
        "property_type": "1BHK", "furnishing": "furnished", "preferences": "no brokerage",
    }
    with patch("main.parse_criteria", new=AsyncMock(return_value=mock_result)):
        response = client.post("/criteria/parse", json={"description": "1BHK in Pune near Hinjewadi"})
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Pune"
    assert data["areas"] == ["Hinjewadi"]


def test_list_searches_empty():
    with patch("main.db.list_searches", new=AsyncMock(return_value=[])):
        response = client.get("/searches")
    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && pytest tests/test_api.py::test_health -v
```

Expected: FAIL — `main` module not found.

- [ ] **Step 3: Write main.py**

```python
# backend/main.py
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import ParseCriteriaRequest, ParsedCriteria, CreateSearchRequest, SearchResponse, ListingResponse, SearchWithListings
from db.pool import open_pool, close_pool
from db import postgres_client as db
from llm.parse_criteria import parse_criteria
from agents.orchestrator import OrchestratorAgent
from agents.ranker_agent import RankerAgent
from config import settings
from scraper.session import login_and_save, invalidate_session
from playwright.async_api import async_playwright

# In-memory registry of active orchestrators keyed by search_id
_active_orchestrators: dict[str, OrchestratorAgent] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="Facebook House Hunt", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/criteria/parse", response_model=ParsedCriteria)
async def parse_criteria_endpoint(req: ParseCriteriaRequest):
    """Parse natural language description into structured search criteria."""
    result = await parse_criteria(req.description)
    return result


@app.get("/searches")
async def list_searches():
    """List all past searches for the dashboard."""
    return await db.list_searches()


@app.get("/searches/{search_id}")
async def get_search(search_id: str):
    """Get a search and all its listings."""
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    listings = await db.list_listings(search_id)
    return {"search": search, "listings": listings}


@app.post("/searches")
async def create_search(req: CreateSearchRequest, background_tasks: BackgroundTasks):
    """Create a new search and start the agent pipeline."""
    search = await db.create_search(
        city=req.city,
        areas=req.areas,
        budget_max=req.budget_max,
        property_type=req.property_type,
        furnishing=req.furnishing,
        preferences=req.preferences,
        raw_description=req.raw_description,
    )
    search_id = search["id"]

    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=req.city,
        areas=req.areas,
        budget_max=req.budget_max,
        property_type=req.property_type,
        furnishing=req.furnishing,
        preferences=req.preferences,
    )
    _active_orchestrators[search_id] = orchestrator
    background_tasks.add_task(orchestrator.run)
    return search


@app.get("/searches/{search_id}/stream")
async def stream_search(search_id: str):
    """SSE stream of live agent events for an active search."""
    orchestrator = _active_orchestrators.get(search_id)

    async def generate():
        if orchestrator is None:
            # Search completed before client connected — use RankerAgent to stream sorted listings
            ranker = RankerAgent()
            queue: asyncio.Queue = asyncio.Queue()
            total = await ranker.rank_and_stream(search_id, queue)
            while not queue.empty():
                event = await queue.get()
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            search = await db.get_search(search_id)
            status = search.get("status", "completed") if search else "completed"
            yield f"event: complete\ndata: {json.dumps({'total': total, 'status': status})}\n\n"
            return

        async for event in orchestrator.event_stream():
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

        # Clean up after stream ends
        _active_orchestrators.pop(search_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/searches/{search_id}/extend")
async def extend_search(search_id: str, background_tasks: BackgroundTasks):
    """Extend an existing search with more groups / broader areas."""
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    current_listings = await db.list_listings(search_id)
    extend_offset = len(current_listings)  # skip already-fetched groups (approx)

    await db.update_search_status(search_id, "running")

    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=search["city"],
        areas=search["areas"],
        budget_max=search["budget_max"],
        property_type=search["property_type"],
        furnishing=search["furnishing"],
        preferences=search["preferences"],
    )
    _active_orchestrators[search_id] = orchestrator
    background_tasks.add_task(orchestrator.run, extend=True, extend_offset=extend_offset)
    return {"status": "extending", "search_id": search_id}


@app.post("/fb/login")
async def fb_login():
    """Trigger a fresh Facebook login (invalidates saved session)."""
    invalidate_session()
    try:
        async with async_playwright() as pw:
            await login_and_save(pw)
        return {"status": "ok", "message": "Facebook login successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run API tests**

```bash
cd backend && pytest tests/test_api.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Start the backend and verify it runs**

```bash
cd backend && uvicorn main:app --reload --port 8000
```

Expected: `Application startup complete.`

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_api.py
git commit -m "feat: FastAPI app with SSE streaming and all endpoints"
```

---

## Task 13: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/globals.css`

- [ ] **Step 1: Scaffold Next.js project**

```bash
cd /path/to/Facebook-House-Hunt
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir no --import-alias "@/*"
```

Answer prompts: TypeScript=yes, ESLint=yes, Tailwind=yes, `src/` dir=no, App Router=yes, import alias=`@/*`.

- [ ] **Step 2: Install additional dependencies**

```bash
cd frontend
npm install
```

- [ ] **Step 3: Write globals.css (dark theme base)**

```css
/* frontend/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #0f172a;
  --foreground: #f8fafc;
}

body {
  background-color: #0f172a;
  color: #f8fafc;
  font-family: 'Inter', sans-serif;
}
```

- [ ] **Step 4: Write layout.tsx**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Facebook House Hunt",
  description: "Find your next home from Facebook group listings",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-slate-950 text-slate-100`}>
        <nav className="border-b border-slate-800 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-sky-400">🏠 House Hunt</a>
            <a
              href="/search/new"
              className="bg-sky-500 hover:bg-sky-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              + New Search
            </a>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Write next.config.ts to allow Facebook image domains**

```ts
// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.scontent.xx.fbcdn.net" },
      { protocol: "https", hostname: "**.fbcdn.net" },
      { protocol: "https", hostname: "scontent.xx.fbcdn.net" },
    ],
  },
};

export default nextConfig;
```

- [ ] **Step 6: Add .env.local for frontend**

```
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 7: Start frontend and verify it builds**

```bash
cd frontend && npm run dev
```

Expected: `Ready on http://localhost:3000`

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: Next.js frontend scaffold with dark theme"
```

---

## Task 14: Frontend API Client and SSE Hook

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/sse.ts`

- [ ] **Step 1: Write api.ts**

```typescript
// frontend/lib/api.ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ParsedCriteria {
  city: string;
  areas: string[];
  budget_max: number | null;
  property_type: string | null;
  furnishing: string | null;
  preferences: string | null;
}

export interface Search {
  id: string;
  city: string;
  areas: string[];
  budget_max: number | null;
  property_type: string | null;
  furnishing: string | null;
  preferences: string | null;
  raw_description: string | null;
  status: string;
  created_at: string;
  listing_count?: number;
  top_score?: number | null;
}

export interface Listing {
  id: string;
  search_id: string;
  fb_post_url: string;
  group_name: string | null;
  poster_name: string | null;
  posted_at: string | null;
  raw_text: string | null;
  image_urls: string[];
  extracted_rent: number | null;
  extracted_area: string | null;
  extracted_type: string | null;
  extracted_furnishing: string | null;
  summary: string | null;
  match_score: number | null;
  score_breakdown: Record<string, number> | null;
  created_at: string;
}

export async function parseCriteria(description: string): Promise<ParsedCriteria> {
  const res = await fetch(`${API}/criteria/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error("Parse failed");
  return res.json();
}

export async function listSearches(): Promise<Search[]> {
  const res = await fetch(`${API}/searches`);
  if (!res.ok) throw new Error("Failed to load searches");
  return res.json();
}

export async function getSearch(id: string): Promise<{ search: Search; listings: Listing[] }> {
  const res = await fetch(`${API}/searches/${id}`);
  if (!res.ok) throw new Error("Search not found");
  return res.json();
}

export async function createSearch(criteria: Omit<ParsedCriteria, never> & { raw_description?: string }): Promise<Search> {
  const res = await fetch(`${API}/searches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(criteria),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}

export async function extendSearch(id: string): Promise<void> {
  const res = await fetch(`${API}/searches/${id}/extend`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to extend search");
}
```

- [ ] **Step 2: Write sse.ts**

```typescript
// frontend/lib/sse.ts
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SSEEvent =
  | { event: "status"; data: { message: string; status: string } }
  | { event: "listing"; data: Record<string, unknown> }
  | { event: "complete"; data: { total: number; high_match?: number; status: string } }
  | { event: "error"; data: { message: string } };

export function useSSE(searchId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!searchId || esRef.current) return;

    const es = new EventSource(`${API}/searches/${searchId}/stream`);
    esRef.current = es;
    setIsConnected(true);

    const handleEvent = (eventName: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setEvents(prev => [...prev, { event: eventName, data } as SSEEvent]);
        if (eventName === "complete" || eventName === "error") {
          setIsDone(true);
          es.close();
          esRef.current = null;
          setIsConnected(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.addEventListener("status", handleEvent("status"));
    es.addEventListener("listing", handleEvent("listing"));
    es.addEventListener("complete", handleEvent("complete"));
    es.addEventListener("error", handleEvent("error"));

    es.onerror = () => {
      setIsConnected(false);
      es.close();
      esRef.current = null;
    };
  }, [searchId]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  const statusMessages = events
    .filter(e => e.event === "status")
    .map(e => (e as { event: "status"; data: { message: string; status: string } }).data.message);

  const listings = events
    .filter(e => e.event === "listing")
    .map(e => (e as { event: "listing"; data: Record<string, unknown> }).data);

  const completeEvent = events.find(e => e.event === "complete") as
    | { event: "complete"; data: { total: number; high_match?: number; status: string } }
    | undefined;

  const errorEvent = events.find(e => e.event === "error") as
    | { event: "error"; data: { message: string } }
    | undefined;

  return { statusMessages, listings, completeEvent, errorEvent, isConnected, isDone };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/
git commit -m "feat: frontend API client and SSE hook"
```

---

## Task 15: SearchHistoryCard and Dashboard

**Files:**
- Create: `frontend/components/SearchHistoryCard.tsx`
- Create: `frontend/app/page.tsx`

- [ ] **Step 1: Write SearchHistoryCard.tsx**

```tsx
// frontend/components/SearchHistoryCard.tsx
import type { Search } from "@/lib/api";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
};

function scoreColor(score: number | null | undefined): string {
  if (!score) return "text-slate-400";
  if (score >= 75) return "text-green-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

export function SearchHistoryCard({ search }: { search: Search }) {
  const statusClass = STATUS_COLORS[search.status] ?? "bg-slate-700 text-slate-300";
  const date = new Date(search.created_at).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <Link href={`/search/${search.id}`}>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-sky-500/50 hover:bg-slate-800/60 transition-all cursor-pointer group">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-slate-100 group-hover:text-sky-400 transition-colors">
              📍 {search.city}
            </h3>
            {search.areas.length > 0 && (
              <p className="text-sm text-slate-400 mt-0.5">
                {search.areas.join(", ")}
              </p>
            )}
          </div>
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusClass}`}>
            {search.status}
          </span>
        </div>

        <div className="flex items-center gap-4 text-sm text-slate-400 mb-3">
          {search.property_type && <span>🏠 {search.property_type}</span>}
          {search.budget_max && <span>₹ {search.budget_max.toLocaleString("en-IN")}/mo</span>}
          {search.furnishing && <span>✨ {search.furnishing}</span>}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">{date}</span>
          <div className="flex items-center gap-3">
            {search.listing_count !== undefined && (
              <span className="text-slate-400">{search.listing_count} listings</span>
            )}
            {search.top_score != null && (
              <span className={`font-bold ${scoreColor(search.top_score)}`}>
                Top: {search.top_score}%
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Write Dashboard page.tsx**

```tsx
// frontend/app/page.tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listSearches, type Search } from "@/lib/api";
import { SearchHistoryCard } from "@/components/SearchHistoryCard";

export default function Dashboard() {
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSearches()
      .then(setSearches)
      .catch(() => setSearches([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-100">Recent Searches</h1>
          <p className="text-slate-400 mt-1">Click a search to view its results</p>
        </div>
        <Link
          href="/search/new"
          className="bg-sky-500 hover:bg-sky-600 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
        >
          + New Search
        </Link>
      </div>

      {loading ? (
        <div className="text-slate-400 text-center py-16">Loading...</div>
      ) : searches.length === 0 ? (
        <div className="text-center py-20 border border-dashed border-slate-700 rounded-2xl">
          <div className="text-5xl mb-4">🏠</div>
          <h2 className="text-xl font-semibold text-slate-300 mb-2">No searches yet</h2>
          <p className="text-slate-500 mb-6">Start your first Facebook house hunt</p>
          <Link
            href="/search/new"
            className="bg-sky-500 hover:bg-sky-600 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Start Searching
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {searches.map(s => <SearchHistoryCard key={s.id} search={s} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/SearchHistoryCard.tsx frontend/app/page.tsx
git commit -m "feat: dashboard with search history"
```

---

## Task 16: SearchInput Component

**Files:**
- Create: `frontend/components/SearchInput.tsx`

- [ ] **Step 1: Write SearchInput.tsx**

```tsx
// frontend/components/SearchInput.tsx
"use client";
import { useState, useEffect, useRef } from "react";
import { parseCriteria, type ParsedCriteria } from "@/lib/api";

interface Props {
  onCriteriaReady: (criteria: ParsedCriteria) => void;
}

const FURNISHING_OPTIONS = ["any", "furnished", "semi-furnished", "unfurnished"];
const TYPE_OPTIONS = ["any", "1BHK", "2BHK", "3BHK", "shared", "studio", "full apartment"];

export function SearchInput({ onCriteriaReady }: Props) {
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState<ParsedCriteria>({
    city: "", areas: [], budget_max: null,
    property_type: null, furnishing: null, preferences: null,
  });
  const [isParsing, setIsParsing] = useState(false);
  const [parsed, setParsed] = useState(false);
  const [areaInput, setAreaInput] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (description.length < 15) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setIsParsing(true);
      try {
        const result = await parseCriteria(description);
        setCriteria(result);
        setAreaInput(result.areas.join(", "));
        setParsed(true);
      } catch {
        // ignore, user can fill manually
      } finally {
        setIsParsing(false);
      }
    }, 1000);
  }, [description]);

  const handleAddArea = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const parts = areaInput.split(",").map(s => s.trim()).filter(Boolean);
      setCriteria(c => ({ ...c, areas: [...new Set([...c.areas, ...parts])] }));
      setAreaInput("");
    }
  };

  const removeArea = (area: string) => {
    setCriteria(c => ({ ...c, areas: c.areas.filter(a => a !== area) }));
  };

  const handleStart = () => {
    const finalAreas = areaInput
      ? [...new Set([...criteria.areas, ...areaInput.split(",").map(s => s.trim()).filter(Boolean)])]
      : criteria.areas;
    onCriteriaReady({ ...criteria, areas: finalAreas, raw_description: description } as ParsedCriteria & { raw_description?: string });
  };

  return (
    <div className="space-y-5">
      {/* NL Input */}
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
        <label className="text-xs text-slate-400 uppercase tracking-wider block mb-2">
          Describe what you&apos;re looking for
        </label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder={`e.g. "Looking for a furnished 1BHK in Pune near Hinjewadi, budget ₹15,000, no brokerage"`}
          rows={3}
          className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm resize-none focus:outline-none"
        />
        {isParsing && (
          <div className="flex items-center gap-2 mt-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400">Analysing with Ollama...</span>
          </div>
        )}
        {parsed && !isParsing && (
          <span className="text-xs text-sky-400 mt-2 block">✨ Fields auto-filled — edit below if needed</span>
        )}
      </div>

      {/* Structured Fields */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-slate-400 block mb-1">City *</label>
          <input
            value={criteria.city}
            onChange={e => setCriteria(c => ({ ...c, city: e.target.value }))}
            placeholder="e.g. Pune"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
        <div className="col-span-2 md:col-span-1">
          <label className="text-xs text-slate-400 block mb-1">Max Budget (₹/mo)</label>
          <input
            type="number"
            value={criteria.budget_max ?? ""}
            onChange={e => setCriteria(c => ({ ...c, budget_max: e.target.value ? parseInt(e.target.value) : null }))}
            placeholder="e.g. 15000"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Property Type</label>
          <select
            value={criteria.property_type ?? "any"}
            onChange={e => setCriteria(c => ({ ...c, property_type: e.target.value === "any" ? null : e.target.value }))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          >
            {TYPE_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-400 block mb-1">Furnishing</label>
          <select
            value={criteria.furnishing ?? "any"}
            onChange={e => setCriteria(c => ({ ...c, furnishing: e.target.value === "any" ? null : e.target.value }))}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          >
            {FURNISHING_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div className="col-span-2 md:col-span-3">
          <label className="text-xs text-slate-400 block mb-1">Areas / Localities (press Enter or comma to add)</label>
          <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 flex flex-wrap gap-1.5 min-h-[40px]">
            {criteria.areas.map(area => (
              <span key={area} className="bg-sky-500/20 text-sky-300 text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                {area}
                <button onClick={() => removeArea(area)} className="hover:text-red-400">×</button>
              </span>
            ))}
            <input
              value={areaInput}
              onChange={e => setAreaInput(e.target.value)}
              onKeyDown={handleAddArea}
              placeholder={criteria.areas.length === 0 ? "e.g. Hinjewadi, Baner" : ""}
              className="bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none flex-1 min-w-[120px]"
            />
          </div>
        </div>
        <div className="col-span-2 md:col-span-3">
          <label className="text-xs text-slate-400 block mb-1">Other Preferences</label>
          <input
            value={criteria.preferences ?? ""}
            onChange={e => setCriteria(c => ({ ...c, preferences: e.target.value || null }))}
            placeholder="e.g. no brokerage, near metro, female preferred"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
          />
        </div>
      </div>

      <button
        onClick={handleStart}
        disabled={!criteria.city.trim()}
        className="w-full bg-sky-500 hover:bg-sky-600 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold py-3 rounded-xl transition-colors"
      >
        ▶ Start Searching Facebook Groups
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/SearchInput.tsx
git commit -m "feat: NL search input with Ollama auto-parse and editable fields"
```

---

## Task 17: New Search Page

**Files:**
- Create: `frontend/app/search/new/page.tsx`

- [ ] **Step 1: Write new search page**

```tsx
// frontend/app/search/new/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSearch, type ParsedCriteria } from "@/lib/api";
import { SearchInput } from "@/components/SearchInput";

export default function NewSearchPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async (criteria: ParsedCriteria & { raw_description?: string }) => {
    if (!criteria.city.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const search = await createSearch(criteria);
      router.push(`/search/${search.id}`);
    } catch (e) {
      setError("Failed to start search. Is the backend running?");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-100 mb-2">New House Hunt</h1>
        <p className="text-slate-400">
          Describe what you&apos;re looking for and we&apos;ll search Facebook groups for you.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-4 animate-pulse">🔍</div>
          <p className="text-slate-300 font-medium">Starting your search...</p>
          <p className="text-slate-500 text-sm mt-1">Redirecting to results</p>
        </div>
      ) : (
        <>
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 mb-5 text-sm">
              {error}
            </div>
          )}
          <SearchInput onCriteriaReady={handleStart} />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/search/new/
git commit -m "feat: new search page with criteria input flow"
```

---

## Task 18: ListingCard and AgentStatusPanel

**Files:**
- Create: `frontend/components/ListingCard.tsx`
- Create: `frontend/components/AgentStatusPanel.tsx`

- [ ] **Step 1: Write ListingCard.tsx**

```tsx
// frontend/components/ListingCard.tsx
import type { Listing } from "@/lib/api";

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 75 ? "bg-green-500" : score >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <span className={`${color} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {score}%
    </span>
  );
}

function borderColor(score: number | null): string {
  if (!score) return "border-slate-700";
  if (score >= 75) return "border-l-green-500";
  if (score >= 50) return "border-l-yellow-500";
  return "border-l-red-500";
}

export function ListingCard({ listing }: { listing: Listing }) {
  const relativeDate = listing.posted_at
    ? new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round((new Date(listing.posted_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
        "day"
      )
    : null;

  return (
    <div className={`bg-slate-900 border border-slate-800 border-l-4 ${borderColor(listing.match_score)} rounded-xl p-4 flex gap-4 hover:bg-slate-800/60 transition-colors`}>
      {/* Image */}
      {listing.image_urls.length > 0 && (
        <div className="w-24 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-slate-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={listing.image_urls[0]}
            alt="Listing"
            className="w-full h-full object-cover"
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {listing.extracted_type && (
                <span className="font-semibold text-slate-100 text-sm">{listing.extracted_type}</span>
              )}
              {listing.extracted_area && (
                <span className="text-slate-400 text-sm">in {listing.extracted_area}</span>
              )}
            </div>
            {listing.extracted_rent && (
              <p className="text-green-400 font-semibold text-sm">
                ₹{listing.extracted_rent.toLocaleString("en-IN")}/mo
                {listing.extracted_furnishing && (
                  <span className="text-slate-400 font-normal ml-1.5">• {listing.extracted_furnishing}</span>
                )}
              </p>
            )}
          </div>
          <ScoreBadge score={listing.match_score} />
        </div>

        {listing.summary && (
          <p className="text-slate-400 text-xs leading-relaxed mb-2 line-clamp-2">{listing.summary}</p>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          {listing.group_name && (
            <span className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded-full">{listing.group_name}</span>
          )}
          {relativeDate && (
            <span className="text-slate-500 text-xs">{relativeDate}</span>
          )}
          <a
            href={listing.fb_post_url}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 text-xs px-2.5 py-0.5 rounded-full transition-colors ml-auto"
          >
            → View on Facebook
          </a>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write AgentStatusPanel.tsx**

```tsx
// frontend/components/AgentStatusPanel.tsx
"use client";

interface Props {
  messages: string[];
  isConnected: boolean;
  isDone: boolean;
  listingCount: number;
  onExtend?: () => void;
  search: {
    city: string;
    areas: string[];
    budget_max: number | null;
    property_type: string | null;
    furnishing: string | null;
  };
}

export function AgentStatusPanel({ messages, isConnected, isDone, listingCount, onExtend, search }: Props) {
  const latestMessage = messages[messages.length - 1] ?? null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4 sticky top-4">
      {/* Search criteria summary */}
      <div>
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Search</p>
        <div className="space-y-1 text-sm">
          <div className="flex items-center gap-1.5 text-slate-200">
            <span>📍</span>
            <span className="font-medium">{search.city}</span>
          </div>
          {search.areas.length > 0 && (
            <div className="text-slate-400 text-xs pl-5">{search.areas.join(", ")}</div>
          )}
          {search.property_type && (
            <div className="text-slate-400 text-xs pl-5">🏠 {search.property_type}</div>
          )}
          {search.budget_max && (
            <div className="text-slate-400 text-xs pl-5">₹ {search.budget_max.toLocaleString("en-IN")}/mo max</div>
          )}
          {search.furnishing && (
            <div className="text-slate-400 text-xs pl-5">✨ {search.furnishing}</div>
          )}
        </div>
      </div>

      {/* Live status */}
      {!isDone && (
        <div className="bg-slate-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            {isConnected ? (
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            ) : (
              <div className="w-2 h-2 rounded-full bg-slate-500" />
            )}
            <span className="text-xs font-medium text-slate-300">
              {isConnected ? "Agent running..." : "Connecting..."}
            </span>
          </div>
          {latestMessage && (
            <p className="text-xs text-slate-400 leading-relaxed">{latestMessage}</p>
          )}
        </div>
      )}

      {/* Results summary */}
      <div className="border-t border-slate-800 pt-3">
        <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Results</p>
        <p className="text-2xl font-bold text-slate-100">{listingCount}</p>
        <p className="text-xs text-slate-500">matching listings found</p>
      </div>

      {/* Extend search */}
      {isDone && onExtend && (
        <button
          onClick={onExtend}
          className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm py-2 rounded-lg transition-colors border border-slate-700"
        >
          🔍 Extend Search
        </button>
      )}

      {/* Recent log */}
      {messages.length > 1 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Log</p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {[...messages].reverse().slice(0, 20).map((msg, i) => (
              <p key={i} className="text-xs text-slate-500 leading-relaxed">{msg}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ListingCard.tsx frontend/components/AgentStatusPanel.tsx
git commit -m "feat: ListingCard and AgentStatusPanel components"
```

---

## Task 19: Results Page

**Files:**
- Create: `frontend/app/search/[id]/page.tsx`

- [ ] **Step 1: Write results page**

```tsx
// frontend/app/search/[id]/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getSearch, extendSearch, type Search, type Listing } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { ListingCard } from "@/components/ListingCard";
import { AgentStatusPanel } from "@/components/AgentStatusPanel";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [search, setSearch] = useState<Search | null>(null);
  const [storedListings, setStoredListings] = useState<Listing[]>([]);
  const [isExtending, setIsExtending] = useState(false);

  const { statusMessages, listings: streamedListings, completeEvent, errorEvent, isConnected, isDone } = useSSE(id);

  // Load existing search data on mount
  useEffect(() => {
    getSearch(id).then(({ search: s, listings: l }) => {
      setSearch(s);
      if (s.status !== "running") {
        setStoredListings(l as Listing[]);
      }
    }).catch(() => router.push("/"));
  }, [id, router]);

  const handleExtend = async () => {
    if (!id) return;
    setIsExtending(true);
    try {
      await extendSearch(id);
      window.location.reload(); // reconnect SSE
    } catch {
      setIsExtending(false);
    }
  };

  // Merge streamed listings with stored listings (SSE takes priority for active searches)
  const displayListings: Listing[] =
    search?.status === "running" || streamedListings.length > 0
      ? (streamedListings as unknown as Listing[])
      : storedListings;

  if (!search) {
    return (
      <div className="text-slate-400 text-center py-16 animate-pulse">Loading search...</div>
    );
  }

  return (
    <div className="flex gap-6 items-start">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0">
        <AgentStatusPanel
          messages={statusMessages}
          isConnected={isConnected}
          isDone={isDone || search.status !== "running"}
          listingCount={displayListings.length}
          onExtend={isDone || search.status === "completed" ? handleExtend : undefined}
          search={{
            city: search.city,
            areas: search.areas,
            budget_max: search.budget_max,
            property_type: search.property_type,
            furnishing: search.furnishing,
          }}
        />
      </div>

      {/* Main results area */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">
              {displayListings.length > 0
                ? `${displayListings.length} listings found`
                : search.status === "running" ? "Searching..." : "No matching listings"}
            </h1>
            {completeEvent && (
              <p className="text-slate-400 text-sm mt-0.5">
                {completeEvent.data.high_match} strong matches (≥75%)
              </p>
            )}
          </div>
        </div>

        {errorEvent && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 mb-4 text-sm">
            ⚠️ {errorEvent.data.message}
          </div>
        )}

        {displayListings.length === 0 && search.status !== "running" ? (
          <div className="text-center py-16 border border-dashed border-slate-700 rounded-2xl">
            <div className="text-4xl mb-3">😕</div>
            <p className="text-slate-300 font-medium mb-1">No matching listings found</p>
            <p className="text-slate-500 text-sm mb-5">Try extending the search to find more results</p>
            {!isExtending ? (
              <button
                onClick={handleExtend}
                className="bg-sky-500 hover:bg-sky-600 text-white px-5 py-2 rounded-lg font-medium transition-colors text-sm"
              >
                🔍 Extend Search
              </button>
            ) : (
              <p className="text-slate-400 text-sm animate-pulse">Extending search...</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {displayListings.map((listing) => (
              <ListingCard key={listing.id ?? listing.fb_post_url} listing={listing} />
            ))}
            {(search.status === "running" && !isDone) && (
              <div className="border border-dashed border-slate-700 rounded-xl p-4 text-center">
                <p className="text-slate-500 text-sm animate-pulse">⟳ Searching more groups...</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/search/
git commit -m "feat: results page with live SSE streaming and extend search"
```

---

## Task 20: End-to-End Smoke Test

- [ ] **Step 1: Start backend**

```bash
cd backend && uvicorn main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Trigger a criteria parse test via curl**

```bash
curl -X POST http://localhost:8000/criteria/parse \
  -H "Content-Type: application/json" \
  -d '{"description": "1BHK furnished in Pune near Hinjewadi, budget 15000"}'
```

Expected: JSON with `city: "Pune"`, `areas: ["Hinjewadi"]`, etc.

- [ ] **Step 4: Verify dashboard loads at http://localhost:3000**

Expected: "No searches yet" placeholder screen.

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Verify Facebook login works**

```bash
curl -X POST http://localhost:8000/fb/login
```

Expected: `{"status": "ok", "message": "Facebook login successful"}` (will open a headless browser and log in — first run only).

- [ ] **Step 7: Create a test search via UI**

- Open http://localhost:3000/search/new
- Type a description, confirm auto-parsed fields, click Start
- Verify redirect to results page and SSE events appear in the sidebar

- [ ] **Step 8: Final commit**

```bash
git add .
git commit -m "feat: complete Facebook House Hunt application"
```
