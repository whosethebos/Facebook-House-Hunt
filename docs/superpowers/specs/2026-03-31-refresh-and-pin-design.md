# Refresh & Pin Design

**Date:** 2026-03-31
**Status:** Approved

## Summary

After an initial search discovers Facebook groups and scrapes listings, the user can:
1. **Pin** individual listings they like — pinned listings survive any future refresh.
2. **Refresh** — re-scrape the exact same Facebook groups that were used in the original run, replace all non-pinned listings with the latest posts, and stream progress live just like the first run.

## Database Schema Changes

Two additive column changes, no new tables:

```sql
-- Store the group URLs discovered during the first run
ALTER TABLE searches ADD COLUMN group_urls TEXT[] DEFAULT '{}';

-- Pin flag on listings; pinned rows survive refresh
ALTER TABLE listings ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT FALSE;
```

`group_urls` is `{}` until discovery completes. Refresh is unavailable (button hidden/disabled) when it is empty.

On refresh, non-pinned listings are deleted before re-scraping:
```sql
DELETE FROM listings WHERE search_id = $1 AND is_pinned = FALSE;
```

## Backend

### `postgres_client.py` — three new functions

| Function | Purpose |
|---|---|
| `save_group_urls(search_id, urls)` | Called after discovery succeeds; persists group URLs |
| `delete_unpinned_listings(search_id)` | Called at refresh start; clears non-pinned rows |
| `toggle_pin(listing_id)` | Flips `is_pinned`; returns updated listing row |

### `orchestrator.py`

- Add `group_urls: list[str]` as an optional Pydantic field (default `[]`).
- When `group_urls` is non-empty, **skip** `GroupDiscoveryAgent` and pass them directly to `ScraperAgent`.
- After a normal first run, call `save_group_urls` immediately after discovery succeeds.

### `main.py` — two new endpoints

**`POST /searches/{id}/refresh`**
1. Load search; 404 if not found.
2. Error 400 if `group_urls` is empty (no groups saved yet).
3. Call `delete_unpinned_listings(search_id)`.
4. Set search status to `running`.
5. Create `OrchestratorAgent` with stored `group_urls`.
6. Register in `_active_orchestrators` and start as background task.
7. Return `{"status": "refreshing", "search_id": id}`.

**`PATCH /listings/{id}/pin`**
1. Call `toggle_pin(listing_id)`.
2. Return updated listing; 404 if not found.

### `models.py`

- Add `is_pinned: bool` to `ListingResponse`.
- Add `group_urls: list[str]` to `SearchResponse`.

## Frontend

### `lib/api.ts`
- `refreshSearch(id: string)` — `POST /searches/{id}/refresh`
- `togglePin(listingId: string)` — `PATCH /listings/{listingId}/pin`, returns `Listing`

### `ListingCard.tsx`
- Pin icon button (📌) in the top-right corner of each card.
- On click: calls `togglePin`, flips local `is_pinned` state optimistically.
- Pinned cards show a subtle accent border to distinguish them visually.

### `AgentStatusPanel.tsx`
- Add **Refresh** button alongside the existing Extend button.
- Visible only when: search is completed AND `group_urls.length > 0`.
- On click: calls `refreshSearch(id)` then `window.location.reload()` — identical pattern to Extend, reconnects to SSE stream automatically.

### `app/search/[id]/page.tsx`
- No changes needed. Refresh sets search status back to `running`, which the existing SSE + streaming logic handles correctly.
- Pass `group_urls` from the search object down to `AgentStatusPanel` so it can conditionally show the Refresh button.

## Data Flow

```
First run:
  POST /searches → discover groups → save_group_urls() → scrape → analyse → complete

Refresh:
  POST /searches/{id}/refresh
    → delete_unpinned_listings()
    → OrchestratorAgent(group_urls=[...])  ← skips discovery
    → scrape same groups → analyse → complete
    (pinned listings untouched throughout)

Pin toggle:
  PATCH /listings/{id}/pin → toggle is_pinned → return updated listing
```

## Error Handling

- Refresh on a search with no stored groups returns HTTP 400.
- If a refresh is already running (search status = `running`), the endpoint returns HTTP 409.
- Pin toggle on a non-existent listing returns HTTP 404.
