# Facebook House Hunt — Design Spec
**Date:** 2026-03-28
**Status:** Approved

---

## Overview

A local web application that automates searching Facebook groups for house/flat rental listings. The user describes what they're looking for in natural language, the system parses the criteria, scrapes relevant Facebook groups using Playwright, analyses posts with a local Ollama LLM, and streams matching results live to the UI. Past searches are saved and accessible from a dashboard.

---

## Project Structure

```
Facebook-House-Hunt/
  backend/
    main.py                  # FastAPI app, SSE endpoints
    config.py                # Settings, env vars
    models.py                # Pydantic request/response models
    agents/
      orchestrator.py        # Google ADK OrchestratorAgent
      group_discovery.py     # GroupDiscoveryAgent
      scraper_agent.py       # ScraperAgent (Playwright)
      analyst_agent.py       # AnalystAgent (Ollama)
      ranker_agent.py        # RankerAgent
    scraper/
      facebook.py            # Playwright Facebook login + group search + post extraction
      session.py             # Session persistence (save/load fb_session.json)
    llm/
      ollama_client.py       # Ollama HTTP client
      analyze.py             # Post analysis + weighted scoring
      parse_criteria.py      # NL → structured criteria extraction
    db/
      pool.py                # asyncpg connection pool
      postgres_client.py     # DB queries (searches, listings)
    session/
      fb_session.json        # Playwright saved Facebook session (gitignored)
    requirements.txt
    .env
  frontend/
    app/
      page.tsx               # Dashboard — search history
      search/
        new/page.tsx         # New search (NL input → parsed fields → start)
        [id]/
          page.tsx           # Results page for a specific search
    components/
      SearchInput.tsx        # NL text box + parsed fields display
      ListingCard.tsx        # Individual listing card with match score
      AgentStatusPanel.tsx   # Live SSE status stream sidebar panel
      SearchHistoryCard.tsx  # Past search card on dashboard
    lib/
      api.ts                 # API client functions
      sse.ts                 # SSE hook for streaming events
    ...next.config.ts, tailwind, etc.
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS, TypeScript |
| Backend | Python FastAPI, asyncpg, SSE via `StreamingResponse` |
| Agents | Google ADK (Ollama as LLM backend) |
| LLM | Ollama (local), model configurable via `.env` |
| Scraping | Playwright (async, headless Chromium) |
| Database | PostgreSQL (local) |
| Session | Playwright storage state saved to `backend/session/fb_session.json` |

---

## UI Flow

### Phase 1 — New Search (natural language → structured criteria)

1. User lands on the dashboard (`/`), clicks "New Search"
2. Navigates to `/search/new`
3. User types a free-text description: *"Looking for a furnished 1BHK in Pune near Hinjewadi, budget ₹15,000, no brokerage"*
4. On input completion (debounced), frontend calls `POST /criteria/parse` → Ollama extracts:
   - City: Pune
   - Areas: [Hinjewadi]
   - Budget max: 15000
   - Property type: 1BHK
   - Furnishing: Furnished
   - Preferences: no brokerage
5. Extracted values auto-populate editable structured fields below the text box
6. User reviews and edits fields if needed
7. User clicks **"Start Searching Facebook Groups"**

### Phase 2 — Live Search Results (`/search/[id]`)

- Sidebar: editable filter panel + live **Agent Status** panel (SSE-driven)
- Main area: listing cards stream in as the agent finds and scores them
- Each card shows: image(s), title, rent, area, match score (colour-coded), group name, post date, "View on Facebook" button (opens original post URL)
- When search completes, a summary appears: "Found X listings, Y are strong matches"
- **Extend Search** button: triggers another round with more groups or wider area

### Dashboard (`/`)

- Lists all past searches with: city, areas, date, total listings found, top match score, status badge
- Clicking a past search → navigates to `/search/[id]` and loads saved results from DB (no re-scraping)
- "New Search" button prominent at top

---

## Agent Pipeline

### OrchestratorAgent

Coordinates the full pipeline. Yields SSE events throughout.

```
1. Create search record in DB (status: "running")
2. Run GroupDiscoveryAgent → get list of group URLs
3. Run ScraperAgent → extract posts from groups
4. Run AnalystAgent → score + store each listing in DB, stream SSE "listing" events as each is scored
5. Run RankerAgent → sort results already in DB by score (no re-storing needed)
6. Update search status to "completed"
7. Yield "complete" SSE event
```

If `extend=True`, repeats from step 2 with expanded group list or additional area search terms.

### GroupDiscoveryAgent

- Searches Facebook for groups matching `"flat flatmates {city}"`, `"flat rent {city}"`, etc.
- Returns top 5–10 group URLs
- Groups are not stored in DB (re-discovered each search)

### ScraperAgent

For each group × each area in user's area list:
1. Navigate to the group page
2. Use the group's internal search bar to search for the area name (e.g., "Hinjewadi")
3. Sort results by "Recent"
4. Scroll and collect posts from the last 7 days
5. Quick pre-filter: skip posts with zero images (cheap DOM check)
6. Full extraction per post:
   - Post URL
   - Poster name
   - Post date/time
   - Full post text
   - All image URLs
   - Group name
7. Deduplicate across area searches (same post URL = same post)
8. Add random human-like delay (2–5s) between each page action

**Anti-bot measures:**
- Randomised delays between all Playwright actions (2–5s)
- Human-like scroll speed (gradual, not instant)
- Reuse saved Playwright session to avoid repeated logins
- Headless but with realistic viewport (1280×800) and full user-agent string
- No parallel browser sessions (sequential group scraping)

**Facebook session management (`session.py`):**
- On startup, check if `fb_session.json` exists and is < 7 days old
- If valid: load session into Playwright context
- If missing or expired: perform credential-based login using `FB_EMAIL` / `FB_PASSWORD` from `.env`, save new session to `fb_session.json`
- If mid-scrape session expires: auto-re-login and resume

### AnalystAgent

Runs after ScraperAgent completes. For each extracted post:

1. Send post text + user criteria to Ollama
2. Ollama returns structured JSON:
   ```json
   {
     "extracted_rent": 14500,
     "extracted_area": "Hinjewadi Phase 2",
     "extracted_type": "1BHK",
     "extracted_furnishing": "furnished",
     "scores": {
       "area": 28,
       "budget": 25,
       "type": 18,
       "furnishing": 12,
       "preferences": 8
     },
     "total_score": 91,
     "summary": "Furnished 1BHK in Hinjewadi Phase 2, ₹14,500/mo, no brokerage mentioned"
   }
   ```
3. Store results in `listings` table

**Weighted scoring:**
| Criterion | Weight |
|---|---|
| City / area match | 30% |
| Budget within range | 25% |
| Property type | 20% |
| Furnishing | 15% |
| Other preferences | 10% |

Posts scoring below 40% are discarded. Posts with no images are discarded.

### RankerAgent

- Sorts listings by `total_score` descending
- Streams each listing as an SSE `listing` event to the frontend
- Listings appear in the UI in order of relevance

---

## Data Model

```sql
-- One record per user search session
CREATE TABLE searches (
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

-- One record per scraped + analysed Facebook post
CREATE TABLE listings (
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

-- Note: Facebook session is stored as a file at backend/session/fb_session.json
-- (not in DB — file-based is faster for Playwright storage state load)
```

---

## API Endpoints

```
POST /searches                  Create search, start pipeline
GET  /searches                  List all searches (dashboard)
GET  /searches/{id}             Get search + all listings
GET  /searches/{id}/stream      SSE stream of live agent events
POST /searches/{id}/extend      Extend search (more groups / wider area)
POST /criteria/parse            Parse NL description → structured criteria (used client-side for instant feedback)
POST /fb/login                  Trigger manual Facebook re-login
GET  /health                    Health check
```

### SSE Event Types

```jsonl
{"event": "status",   "data": {"message": "Searching group: Flat & Flatmates Pune...", "status": "scraping"}}
{"event": "status",   "data": {"message": "Found 23 posts across 3 groups in Hinjewadi", "status": "analysing"}}
{"event": "listing",  "data": { ...full listing object... }}
{"event": "complete", "data": {"total": 12, "high_match": 5, "status": "completed"}}
{"event": "error",    "data": {"message": "Facebook session expired, re-logging in..."}}
```

---

## Environment Variables (`.env`)

```
FB_EMAIL=your@email.com
FB_PASSWORD=yourpassword
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
DATABASE_URL=postgresql://localhost:5432/facebook_house_hunt
FRONTEND_URL=http://localhost:3000
```

---

## Error Handling

- **Facebook session expired mid-scrape**: auto-re-login, resume scraping, emit warning SSE event
- **Facebook bot detection** (CAPTCHA / block): emit error SSE event, stop gracefully, surface message in UI ("Facebook rate-limited this session. Try again in a few minutes.")
- **Ollama unreachable**: emit error, mark search as failed, surface in UI
- **No results found**: surface "No matching posts found" in UI with option to extend search
- **Partial results**: if scraping completes but < 3 matches, UI automatically suggests extending search

---

## Extend Search

When the user clicks **Extend Search**:
1. `POST /searches/{id}/extend` is called
2. Orchestrator runs another round with:
   - Additional Facebook groups (next 5 beyond the original set)
   - Broader area terms (e.g., if user specified "Hinjewadi", also search "Hinjewadi Phase 1", "Hinjewadi Phase 2", "Hinjewadi Phase 3")
3. New listings are appended to the existing results in the UI
4. Duplicates (same `fb_post_url`) are automatically skipped

---

## Out of Scope

- Video extraction from posts (images only for now)
- Email/push notifications for new listings
- User accounts / authentication
- Mobile app
- Facebook Marketplace (groups only)
