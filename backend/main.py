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
from llm.analyze import analyze_post
from playwright.async_api import async_playwright

# In-memory registry of active orchestrators keyed by search_id
_active_orchestrators: dict[str, OrchestratorAgent] = {}
# Pending Facebook login confirmation events keyed by search_id
_login_confirm_events: dict[str, asyncio.Event] = {}


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


@app.delete("/searches/{search_id}", status_code=204)
async def delete_search(search_id: str):
    """Delete a search and all its listings."""
    found = await db.delete_search(search_id)
    if not found:
        raise HTTPException(status_code=404, detail="Search not found")


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

    login_event = asyncio.Event()
    _login_confirm_events[search_id] = login_event
    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=req.city,
        areas=req.areas,
        budget_max=req.budget_max,
        property_type=req.property_type,
        furnishing=req.furnishing,
        preferences=req.preferences,
        login_confirm_event=login_event,
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
        _login_confirm_events.pop(search_id, None)

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

    login_event = asyncio.Event()
    _login_confirm_events[search_id] = login_event
    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=search["city"],
        areas=search["areas"],
        budget_max=search["budget_max"],
        property_type=search["property_type"],
        furnishing=search["furnishing"],
        preferences=search["preferences"],
        login_confirm_event=login_event,
    )
    _active_orchestrators[search_id] = orchestrator
    background_tasks.add_task(orchestrator.run, extend=True, extend_offset=extend_offset)
    return {"status": "extending", "search_id": search_id}


@app.post("/searches/{search_id}/refresh")
async def refresh_search(search_id: str, background_tasks: BackgroundTasks):
    """Re-scrape the same groups as the original search, preserving pinned listings."""
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    if not search.get("group_urls"):
        raise HTTPException(status_code=400, detail="No groups stored - run the original search first")
    if search.get("status") == "running":
        raise HTTPException(status_code=409, detail="Search is already running")

    await db.update_search_status(search_id, "running")
    await db.delete_unpinned_listings(search_id)

    login_event = asyncio.Event()
    _login_confirm_events[search_id] = login_event
    orchestrator = OrchestratorAgent(
        search_id=search_id,
        city=search["city"],
        areas=search["areas"],
        budget_max=search["budget_max"],
        property_type=search["property_type"],
        furnishing=search["furnishing"],
        preferences=search["preferences"],
        group_urls=search["group_urls"],
        login_confirm_event=login_event,
    )
    _active_orchestrators[search_id] = orchestrator
    background_tasks.add_task(orchestrator.run, extend=False)
    return {"status": "refreshing", "search_id": search_id}


@app.post("/listings/{listing_id}/analyze", response_model=ListingResponse)
async def analyze_listing(listing_id: str):
    """Run Ollama analysis on a single listing and persist the score."""
    listing = await db.get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    search = await db.get_search(listing["search_id"])
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    result = await analyze_post(
        post_text=listing.get("raw_text") or "",
        city=search["city"],
        areas=search.get("areas") or [],
        budget_max=search.get("budget_max"),
        property_type=search.get("property_type"),
        furnishing=search.get("furnishing"),
        preferences=search.get("preferences"),
    )

    updated = await db.update_listing_analysis(
        listing_id=listing_id,
        extracted_rent=result["extracted_rent"],
        extracted_area=result["extracted_area"],
        extracted_type=result["extracted_type"],
        extracted_furnishing=result["extracted_furnishing"],
        summary=result["summary"],
        match_score=result["match_score"],
        score_breakdown=result["score_breakdown"],
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to save analysis")
    return updated


@app.patch("/listings/{listing_id}/pin", response_model=ListingResponse)
async def pin_listing(listing_id: str):
    """Toggle the is_pinned flag on a listing."""
    listing = await db.toggle_pin(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@app.post("/searches/{search_id}/fb-login-confirm")
async def confirm_fb_login(search_id: str):
    """Signal that the user has completed Facebook login (including any 2FA) in the browser."""
    event = _login_confirm_events.pop(search_id, None)
    if event is None:
        raise HTTPException(status_code=404, detail="No pending Facebook login for this search")
    event.set()
    return {"status": "ok"}


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
