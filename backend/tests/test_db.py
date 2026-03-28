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
