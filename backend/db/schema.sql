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

CREATE INDEX IF NOT EXISTS idx_searches_created_at ON searches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_search_score ON listings(search_id, match_score DESC);
