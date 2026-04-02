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
  group_urls: string[];
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
  is_pinned: boolean;
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

export async function deleteSearch(id: string): Promise<void> {
  const res = await fetch(`${API}/searches/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete search");
}

export async function extendSearch(id: string): Promise<void> {
  const res = await fetch(`${API}/searches/${id}/extend`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to extend search");
}

export async function refreshSearch(id: string): Promise<void> {
  const res = await fetch(`${API}/searches/${id}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh search");
}

export async function togglePin(listingId: string): Promise<Listing> {
  const res = await fetch(`${API}/listings/${listingId}/pin`, { method: "PATCH" });
  if (!res.ok) throw new Error("Failed to toggle pin");
  return res.json();
}

export async function analyzeListing(listingId: string): Promise<Listing> {
  const res = await fetch(`${API}/listings/${listingId}/analyze`, { method: "POST" });
  if (!res.ok) throw new Error("Analysis failed");
  return res.json();
}

export async function confirmFbLogin(searchId: string): Promise<void> {
  const res = await fetch(`${API}/searches/${searchId}/fb-login-confirm`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to confirm Facebook login");
}
