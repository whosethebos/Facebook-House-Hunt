# Refresh & Pin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pin listings they like, and refresh a completed search to re-scrape the same Facebook groups while preserving pinned listings.

**Architecture:** Two new DB columns (`searches.group_urls`, `listings.is_pinned`) feed a skip-discovery mode in the orchestrator, exposed via two new API endpoints (`POST /searches/{id}/refresh`, `PATCH /listings/{id}/pin`) and surfaced in the frontend via a pin button on each listing card and a Refresh button in the sidebar.

**Tech Stack:** Python 3.12, FastAPI, psycopg3, PostgreSQL, Next.js 15, TypeScript, Playwright

---

## File Map

| File | Change |
|---|---|
| `backend/db/schema.sql` | Add two columns |
| `backend/db/postgres_client.py` | Three new DB functions |
| `backend/models.py` | Add `group_urls` + `is_pinned` fields |
| `backend/agents/orchestrator.py` | Add `group_urls` field; skip discovery when provided; save groups after discovery |
| `backend/main.py` | Two new endpoints: `/refresh` and `/pin` |
| `backend/tests/test_api.py` | Tests for both new endpoints |
| `frontend/lib/api.ts` | Update interfaces; add `refreshSearch` + `togglePin` |
| `frontend/components/ListingCard.tsx` | Convert to client component; add pin button |
| `frontend/components/AgentStatusPanel.tsx` | Add `onRefresh` + `hasGroups` props; show Refresh button |
| `frontend/app/search/[id]/page.tsx` | Wire up `handleRefresh`; pass `group_urls` to sidebar |

---

### Task 1: DB Schema Migration

**Files:**
- Modify: `backend/db/schema.sql`

- [ ] **Step 1: Add columns to schema.sql**

Open `backend/db/schema.sql` and replace the two `CREATE TABLE` blocks with:

```sql
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
    group_urls TEXT[] NOT NULL DEFAULT '{}',
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
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(search_id, fb_post_url)
);

CREATE INDEX IF NOT EXISTS idx_searches_created_at ON searches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_search_score ON listings(search_id, match_score DESC);
```

- [ ] **Step 2: Apply migration to the running database**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/backend
psql postgresql://postgres:postgres@127.0.0.1:5432/facebook_house_hunt \
  -c "ALTER TABLE searches ADD COLUMN IF NOT EXISTS group_urls TEXT[] NOT NULL DEFAULT '{}';"
psql postgresql://postgres:postgres@127.0.0.1:5432/facebook_house_hunt \
  -c "ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE;"
```

Expected: `ALTER TABLE` printed twice, no errors.

- [ ] **Step 3: Verify columns exist**

```bash
psql postgresql://postgres:postgres@127.0.0.1:5432/facebook_house_hunt \
  -c "\d searches" | grep group_urls
psql postgresql://postgres:postgres@127.0.0.1:5432/facebook_house_hunt \
  -c "\d listings" | grep is_pinned
```

Expected: one line each showing the column name and type.

- [ ] **Step 4: Commit**

```bash
git add backend/db/schema.sql
git commit -m "feat: add group_urls to searches and is_pinned to listings"
```

---

### Task 2: DB Client Functions

**Files:**
- Modify: `backend/db/postgres_client.py`

- [ ] **Step 1: Add three functions at the end of the file**

Append to `backend/db/postgres_client.py`:

```python
async def save_group_urls(search_id: str, urls: list[str]) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE searches SET group_urls = %s WHERE id = %s",
            (urls, search_id),
        )


async def delete_unpinned_listings(search_id: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "DELETE FROM listings WHERE search_id = %s AND is_pinned = FALSE",
            (search_id,),
        )


async def toggle_pin(listing_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "UPDATE listings SET is_pinned = NOT is_pinned WHERE id = %s RETURNING *",
            (listing_id,),
        )
        row = await cur.fetchone()
        return _row(row) if row else None
```

- [ ] **Step 2: Commit**

```bash
git add backend/db/postgres_client.py
git commit -m "feat: add save_group_urls, delete_unpinned_listings, toggle_pin to db client"
```

---

### Task 3: Pydantic Models

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Add `group_urls` to `SearchResponse` and `is_pinned` to `ListingResponse`**

In `backend/models.py`, update `SearchResponse` to add `group_urls` after `top_score`:

```python
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
    created_at: datetime
    listing_count: int = 0
    top_score: int | None = None
    group_urls: list[str] = []
```

Update `ListingResponse` to add `is_pinned` after `score_breakdown`:

```python
class ListingResponse(BaseModel):
    id: str
    search_id: str
    fb_post_url: str
    group_name: str | None
    poster_name: str | None
    posted_at: datetime | None
    raw_text: str | None
    image_urls: list[str]
    extracted_rent: int | None
    extracted_area: str | None
    extracted_type: str | None
    extracted_furnishing: str | None
    summary: str | None
    match_score: int | None
    score_breakdown: dict | None
    is_pinned: bool = False
    created_at: datetime
```

- [ ] **Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add group_urls to SearchResponse and is_pinned to ListingResponse"
```

---

### Task 4: Orchestrator — Skip Discovery Mode

**Files:**
- Modify: `backend/agents/orchestrator.py`

- [ ] **Step 1: Add `group_urls` Pydantic field**

In `backend/agents/orchestrator.py`, add `group_urls` to the declared fields block (after `preferences`):

```python
    search_id: str
    city: str
    areas: list[str]
    budget_max: int | None
    property_type: str | None
    furnishing: str | None
    preferences: str | None
    group_urls: list[str] = []
```

- [ ] **Step 2: Pass `group_urls` through `__init__`**

Update the `__init__` signature and `super().__init__()` call:

```python
    def __init__(self, search_id: str, city: str, areas: list[str],
                 budget_max: int | None, property_type: str | None,
                 furnishing: str | None, preferences: str | None,
                 group_urls: list[str] | None = None):
        super().__init__(
            name="orchestrator_agent",
            description="Coordinates the pipeline",
            search_id=search_id,
            city=city,
            areas=areas,
            budget_max=budget_max,
            property_type=property_type,
            furnishing=furnishing,
            preferences=preferences,
            group_urls=group_urls or [],
        )
        self._queue = asyncio.Queue()
        self._done = False
        self._group_discovery = GroupDiscoveryAgent()
        self._scraper = ScraperAgent()
        self._analyst = AnalystAgent()
        self._ranker = RankerAgent()
```

- [ ] **Step 3: Replace the discovery step in `run()` to save or reuse groups**

In the `run()` method, replace the current `# Step 1: Discover groups` block:

```python
                    # Step 1: Discover groups (or reuse stored ones for refresh)
                    if self.group_urls:
                        groups = self.group_urls
                        await self._queue.put({
                            "event": "status",
                            "data": {
                                "message": f"Using {len(groups)} previously discovered groups",
                                "status": "discovering",
                            },
                        })
                    else:
                        groups = await self._group_discovery.discover(
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
                        await db.save_group_urls(self.search_id, groups)
```

- [ ] **Step 4: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat: orchestrator saves group_urls after discovery, skips discovery on refresh"
```

---

### Task 5: API Endpoints — Refresh and Pin

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add the refresh endpoint**

After the `extend_search` endpoint in `backend/main.py`, add:

```python
@app.post("/searches/{search_id}/refresh")
async def refresh_search(search_id: str, background_tasks: BackgroundTasks):
    """Re-scrape the same groups as the original search, preserving pinned listings."""
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    if not search.get("group_urls"):
        raise HTTPException(status_code=400, detail="No groups stored — run the original search first")
    if search.get("status") == "running":
        raise HTTPException(status_code=409, detail="Search is already running")

    await db.delete_unpinned_listings(search_id)
    await db.update_search_status(search_id, "running")

    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=search["city"],
        areas=search["areas"],
        budget_max=search["budget_max"],
        property_type=search["property_type"],
        furnishing=search["furnishing"],
        preferences=search["preferences"],
        group_urls=search["group_urls"],
    )
    _active_orchestrators[search_id] = orchestrator
    background_tasks.add_task(orchestrator.run)
    return {"status": "refreshing", "search_id": search_id}
```

- [ ] **Step 2: Add the pin toggle endpoint**

After the refresh endpoint, add:

```python
@app.patch("/listings/{listing_id}/pin")
async def pin_listing(listing_id: str):
    """Toggle the is_pinned flag on a listing."""
    listing = await db.toggle_pin(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing
```

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add POST /searches/{id}/refresh and PATCH /listings/{id}/pin endpoints"
```

---

### Task 6: API Endpoint Tests

**Files:**
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests for the refresh endpoint**

Add to `backend/tests/test_api.py`:

```python
def test_refresh_search_no_groups():
    """Returns 400 when no group_urls stored."""
    search_stub = {
        "id": "abc", "city": "Pune", "areas": [], "budget_max": None,
        "property_type": None, "furnishing": None, "preferences": None,
        "raw_description": None, "status": "completed", "group_urls": [],
    }
    with patch("main.db.get_search", new=AsyncMock(return_value=search_stub)):
        response = client.post("/searches/abc/refresh")
    assert response.status_code == 400


def test_refresh_search_already_running():
    """Returns 409 when search is already running."""
    search_stub = {
        "id": "abc", "city": "Pune", "areas": [], "budget_max": None,
        "property_type": None, "furnishing": None, "preferences": None,
        "raw_description": None, "status": "running",
        "group_urls": ["https://www.facebook.com/groups/123"],
    }
    with patch("main.db.get_search", new=AsyncMock(return_value=search_stub)):
        response = client.post("/searches/abc/refresh")
    assert response.status_code == 409


def test_refresh_search_success():
    """Returns 200 and starts background task when groups are stored."""
    search_stub = {
        "id": "abc", "city": "Pune", "areas": ["Hinjewadi"], "budget_max": 15000,
        "property_type": "1BHK", "furnishing": "furnished", "preferences": None,
        "raw_description": None, "status": "completed",
        "group_urls": ["https://www.facebook.com/groups/123"],
    }
    with (
        patch("main.db.get_search", new=AsyncMock(return_value=search_stub)),
        patch("main.db.delete_unpinned_listings", new=AsyncMock()),
        patch("main.db.update_search_status", new=AsyncMock()),
        patch("main.OrchestratorAgent") as MockOrch,
    ):
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock()
        MockOrch.return_value = mock_instance
        response = client.post("/searches/abc/refresh")
    assert response.status_code == 200
    assert response.json()["status"] == "refreshing"


def test_pin_listing_not_found():
    """Returns 404 when listing does not exist."""
    with patch("main.db.toggle_pin", new=AsyncMock(return_value=None)):
        response = client.patch("/listings/nonexistent/pin")
    assert response.status_code == 404


def test_pin_listing_success():
    """Returns updated listing when pin toggle succeeds."""
    listing_stub = {
        "id": "listing-1", "search_id": "abc", "fb_post_url": "https://fb.com/post/1",
        "group_name": None, "poster_name": None, "posted_at": None,
        "raw_text": None, "image_urls": [], "extracted_rent": None,
        "extracted_area": None, "extracted_type": None, "extracted_furnishing": None,
        "summary": None, "match_score": None, "score_breakdown": None,
        "is_pinned": True, "created_at": "2026-03-31T00:00:00+00:00",
    }
    with patch("main.db.toggle_pin", new=AsyncMock(return_value=listing_stub)):
        response = client.patch("/listings/listing-1/pin")
    assert response.status_code == 200
    assert response.json()["is_pinned"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/backend
python -m pytest tests/test_api.py -v -k "refresh or pin"
```

Expected: 5 tests FAIL (endpoints don't exist yet — but since Task 5 was done first, they should now pass. If running in order skip directly to step 3).

- [ ] **Step 3: Run all API tests**

```bash
python -m pytest tests/test_api.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_api.py
git commit -m "test: add tests for refresh and pin endpoints"
```

---

### Task 7: Frontend API Client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add `group_urls` to `Search` interface and `is_pinned` to `Listing` interface**

In `frontend/lib/api.ts`, update the `Search` interface:

```typescript
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
  group_urls: string[];
}
```

Update the `Listing` interface to add `is_pinned`:

```typescript
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
  is_pinned: boolean;
  created_at: string;
}
```

- [ ] **Step 2: Add `refreshSearch` and `togglePin` functions**

Append to `frontend/lib/api.ts`:

```typescript
export async function refreshSearch(id: string): Promise<void> {
  const res = await fetch(`${API}/searches/${id}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh search");
}

export async function togglePin(listingId: string): Promise<Listing> {
  const res = await fetch(`${API}/listings/${listingId}/pin`, { method: "PATCH" });
  if (!res.ok) throw new Error("Failed to toggle pin");
  return res.json();
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add refreshSearch and togglePin to API client; add group_urls and is_pinned to interfaces"
```

---

### Task 8: ListingCard — Pin Button

**Files:**
- Modify: `frontend/components/ListingCard.tsx`

- [ ] **Step 1: Rewrite ListingCard with pin button**

Replace the full contents of `frontend/components/ListingCard.tsx`:

```typescript
"use client";
import { useState } from "react";
import type { Listing } from "@/lib/api";
import { togglePin } from "@/lib/api";

function ScoreRing({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 75 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--error)";
  const bg = `conic-gradient(${color} ${score}%, rgba(255,255,255,0.05) ${score}%)`;
  return (
    <div className="score-ring" style={{ background: bg }}>
      <div className="score-ring-inner" style={{ color }}>
        {score}%
      </div>
    </div>
  );
}

export function ListingCard({ listing, index = 0 }: { listing: Listing; index?: number }) {
  const [isPinned, setIsPinned] = useState(listing.is_pinned ?? false);

  const handlePin = async (e: React.MouseEvent) => {
    e.preventDefault();
    try {
      const updated = await togglePin(listing.id);
      setIsPinned(updated.is_pinned);
    } catch {
      // ignore — UI stays as-is on failure
    }
  };

  const relativeDate = listing.posted_at
    ? new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
        Math.round((new Date(listing.posted_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
        "day"
      )
    : null;

  const accentColor =
    isPinned ? "var(--accent)" :
    listing.match_score && listing.match_score >= 75 ? "var(--success)" :
    listing.match_score && listing.match_score >= 50 ? "var(--warning)" :
    listing.match_score ? "var(--error)" : "var(--border)";

  const delay = Math.min(index, 5);

  return (
    <article
      className={`card animate-fade-up stagger-${delay}`}
      style={{
        padding: "14px 16px",
        display: "flex",
        gap: 14,
        alignItems: "flex-start",
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: "var(--radius)",
      }}
    >
      {/* Thumbnail */}
      {listing.image_urls.length > 0 && (
        <div style={{
          width: 88, height: 72,
          flexShrink: 0,
          borderRadius: 10,
          overflow: "hidden",
          background: "var(--surface)",
        }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={listing.image_urls[0]}
            alt="Listing photo"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title row */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 4 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {listing.extracted_type && (
                <span style={{ fontWeight: 600, color: "var(--text)", fontSize: 14 }}>
                  {listing.extracted_type}
                </span>
              )}
              {listing.extracted_area && (
                <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                  in {listing.extracted_area}
                </span>
              )}
            </div>
            {listing.extracted_rent && (
              <p style={{ margin: "2px 0 0", fontSize: 14, fontWeight: 600, color: "var(--success)" }}>
                ₹{listing.extracted_rent.toLocaleString("en-IN")}/mo
                {listing.extracted_furnishing && (
                  <span style={{ color: "var(--text-muted)", fontWeight: 400, marginLeft: 6, fontSize: 12 }}>
                    · {listing.extracted_furnishing}
                  </span>
                )}
              </p>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <button
              onClick={handlePin}
              title={isPinned ? "Unpin listing" : "Pin listing"}
              style={{
                background: isPinned ? "rgba(129,140,248,0.15)" : "transparent",
                border: `1px solid ${isPinned ? "rgba(129,140,248,0.4)" : "var(--border)"}`,
                borderRadius: "var(--radius-sm)",
                padding: "3px 7px",
                cursor: "pointer",
                fontSize: 13,
                lineHeight: 1,
                color: isPinned ? "var(--accent)" : "var(--text-dim)",
                transition: "all 0.15s",
              }}
            >
              📌
            </button>
            <ScoreRing score={listing.match_score} />
          </div>
        </div>

        {/* Summary */}
        {listing.summary && (
          <p style={{
            color: "var(--text-muted)",
            fontSize: 12,
            lineHeight: 1.6,
            margin: "6px 0 8px",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {listing.summary}
          </p>
        )}

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
          {listing.group_name && (
            <span style={{
              background: "rgba(129,140,248,0.07)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: 11, fontWeight: 500,
              padding: "2px 8px", borderRadius: 100,
            }}>
              {listing.group_name}
            </span>
          )}
          {isPinned && (
            <span style={{
              background: "rgba(129,140,248,0.1)",
              border: "1px solid rgba(129,140,248,0.3)",
              color: "var(--accent)",
              fontSize: 11, fontWeight: 500,
              padding: "2px 8px", borderRadius: 100,
            }}>
              Pinned
            </span>
          )}
          {relativeDate && (
            <span style={{ color: "var(--text-dim)", fontSize: 11 }}>{relativeDate}</span>
          )}
          <a
            href={listing.fb_post_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              marginLeft: "auto",
              background: "rgba(129,140,248,0.1)",
              border: "1px solid rgba(129,140,248,0.2)",
              color: "var(--accent)",
              fontSize: 11, fontWeight: 500,
              padding: "3px 10px", borderRadius: 100,
              textDecoration: "none",
              transition: "background 0.15s, border-color 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            View on Facebook →
          </a>
        </div>
      </div>
    </article>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ListingCard.tsx
git commit -m "feat: add pin button to ListingCard with optimistic toggle"
```

---

### Task 9: AgentStatusPanel — Refresh Button

**Files:**
- Modify: `frontend/components/AgentStatusPanel.tsx`

- [ ] **Step 1: Add `onRefresh` and `hasGroups` to the Props interface**

In `frontend/components/AgentStatusPanel.tsx`, update the `Props` interface:

```typescript
interface Props {
  messages: string[];
  isConnected: boolean;
  isDone: boolean;
  listingCount: number;
  onExtend?: () => void;
  onRefresh?: () => void;
  hasGroups?: boolean;
  search: {
    city: string;
    areas: string[];
    budget_max: number | null;
    property_type: string | null;
    furnishing: string | null;
  };
}
```

- [ ] **Step 2: Destructure the new props and add the Refresh button**

Update the function signature line:

```typescript
export function AgentStatusPanel({ messages, isConnected, isDone, listingCount, onExtend, onRefresh, hasGroups, search }: Props) {
```

Replace the existing `{/* Extend button */}` block with:

```typescript
      {/* Action buttons (Extend + Refresh) */}
      {isDone && (onExtend || (onRefresh && hasGroups)) && (
        <>
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: 0 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {onExtend && (
              <button
                onClick={onExtend}
                className="btn-ghost"
                style={{ width: "100%", justifyContent: "center", fontSize: 13, padding: "8px 0" }}
              >
                Extend Search
              </button>
            )}
            {onRefresh && hasGroups && (
              <button
                onClick={onRefresh}
                className="btn-ghost"
                style={{ width: "100%", justifyContent: "center", fontSize: 13, padding: "8px 0" }}
              >
                Refresh Results
              </button>
            )}
          </div>
        </>
      )}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/AgentStatusPanel.tsx
git commit -m "feat: add Refresh button to AgentStatusPanel"
```

---

### Task 10: Wire Up Results Page

**Files:**
- Modify: `frontend/app/search/[id]/page.tsx`

- [ ] **Step 1: Import `refreshSearch` and add `handleRefresh`**

In `frontend/app/search/[id]/page.tsx`, update the import line:

```typescript
import { getSearch, extendSearch, refreshSearch, type Search, type Listing } from "@/lib/api";
```

Add `handleRefresh` alongside `handleExtend`:

```typescript
  const handleRefresh = async () => {
    if (!id) return;
    try {
      await refreshSearch(id);
      window.location.reload();
    } catch {
      // ignore — user can retry
    }
  };
```

- [ ] **Step 2: Pass `onRefresh` and `hasGroups` to `AgentStatusPanel`**

Update the `<AgentStatusPanel>` JSX to add the two new props:

```typescript
        <AgentStatusPanel
          messages={statusMessages}
          isConnected={isConnected}
          isDone={isDone || search.status !== "running"}
          listingCount={displayListings.length}
          onExtend={isDone || search.status === "completed" ? handleExtend : undefined}
          onRefresh={isDone || search.status === "completed" ? handleRefresh : undefined}
          hasGroups={(search.group_urls?.length ?? 0) > 0}
          search={{
            city: search.city,
            areas: search.areas,
            budget_max: search.budget_max,
            property_type: search.property_type,
            furnishing: search.furnishing,
          }}
        />
```

- [ ] **Step 3: Verify TypeScript compiles and build passes**

```bash
cd /Users/whosethebos/Documents/GitHub/Facebook-House-Hunt/frontend
npx tsc --noEmit
npm run build 2>&1 | tail -20
```

Expected: No type errors. Build completes successfully.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/search/[id]/page.tsx
git commit -m "feat: wire up Refresh button on results page"
```

---

## Done

After all tasks complete, the full flow works as follows:

1. **First run** — completes normally, `group_urls` now saved on the search record.
2. **Pin** — user clicks 📌 on any listing card; it stays pinned across refreshes.
3. **Refresh** — user clicks "Refresh Results" in the sidebar; non-pinned listings are wiped, the orchestrator re-scrapes the same groups, results stream live exactly like the first run.
