# backend/models.py
from pydantic import BaseModel
from datetime import datetime


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
    created_at: datetime
    listing_count: int = 0
    top_score: int | None = None
    group_urls: list[str] = []


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


class SearchWithListings(BaseModel):
    search: SearchResponse
    listings: list[ListingResponse]
