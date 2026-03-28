# backend/llm/analyze.py
from llm.ollama_client import chat_json

_FALLBACK: dict = {
    "extracted_rent": None,
    "extracted_area": None,
    "extracted_type": None,
    "extracted_furnishing": None,
    "match_score": 0,
    "score_breakdown": {},
    "summary": "",
}

_PROMPT = """You are analysing a Facebook house rental post to see how well it matches a user's criteria.

USER CRITERIA:
- City: {city}
- Preferred areas: {areas}
- Max budget: {budget_max}
- Property type: {property_type}
- Furnishing: {furnishing}
- Other preferences: {preferences}

FACEBOOK POST TEXT:
{post_text}

SCORING RULES (allocate points out of the maximum for each criterion):
- area match (max 30): 30 if post is in one of the preferred areas, 15 if nearby, 0 if different area
- budget match (max 25): 25 if rent <= budget_max, 15 if within 20% over, 0 if null budget_max (skip check)
- property type match (max 20): 20 if exact match, 10 if similar, 0 if mismatch or null
- furnishing match (max 15): 15 if exact match, 8 if partial, 0 if mismatch or null
- preferences match (max 10): 10 if all preferences met, 5 if partial, 0 if not met or null

Return a JSON object:
{{
  "extracted_rent": integer or null (monthly rent in INR parsed from post),
  "extracted_area": string or null (locality extracted from post),
  "extracted_type": string or null (e.g. "1BHK", "2BHK", "shared"),
  "extracted_furnishing": string or null (e.g. "furnished", "unfurnished"),
  "scores": {{
    "area": integer,
    "budget": integer,
    "type": integer,
    "furnishing": integer,
    "preferences": integer
  }},
  "total_score": integer (sum of scores above),
  "summary": string (one sentence summary of the listing)
}}"""


async def analyze_post(
    post_text: str,
    city: str,
    areas: list[str],
    budget_max: int | None,
    property_type: str | None,
    furnishing: str | None,
    preferences: str | None,
) -> dict:
    """Score a post against criteria. Returns fallback dict on error."""
    try:
        result = await chat_json([{
            "role": "user",
            "content": _PROMPT.format(
                city=city,
                areas=", ".join(areas) if areas else "any",
                budget_max=f"₹{budget_max}" if budget_max else "not specified",
                property_type=property_type or "any",
                furnishing=furnishing or "any",
                preferences=preferences or "none",
                post_text=post_text[:3000],  # cap to avoid token limits
            ),
        }])
        scores = result.get("scores", {})
        return {
            "extracted_rent": result.get("extracted_rent"),
            "extracted_area": result.get("extracted_area"),
            "extracted_type": result.get("extracted_type"),
            "extracted_furnishing": result.get("extracted_furnishing"),
            "match_score": int(result.get("total_score", 0)),
            "score_breakdown": scores,
            "summary": result.get("summary", ""),
        }
    except Exception:
        return {**_FALLBACK}
