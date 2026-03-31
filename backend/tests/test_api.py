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
