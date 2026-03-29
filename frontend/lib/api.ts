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
