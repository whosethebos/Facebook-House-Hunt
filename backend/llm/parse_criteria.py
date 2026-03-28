# backend/llm/parse_criteria.py
from llm.ollama_client import chat_json

_FALLBACK: dict = {
    "city": "",
    "areas": [],
    "budget_max": None,
    "property_type": None,
    "furnishing": None,
    "preferences": None,
}

_PROMPT = """You are extracting house hunting search criteria from a user's natural language description.

Return a JSON object with exactly these fields:
- city: string (city name, or empty string if not found)
- areas: array of strings (locality/neighbourhood names within the city)
- budget_max: integer (maximum monthly rent in rupees, or null)
- property_type: string — one of "1BHK", "2BHK", "3BHK", "shared", "full apartment", "studio", or null
- furnishing: string — one of "furnished", "semi-furnished", "unfurnished", "any", or null
- preferences: string (any other preferences like "no brokerage", "male only", "near metro", or null)

User description: {description}"""


async def parse_criteria(description: str) -> dict:
    """Extract structured search criteria from natural language. Returns fallback on error."""
    try:
        result = await chat_json([
            {"role": "user", "content": _PROMPT.format(description=description)}
        ])
        return {
            "city": result.get("city", "") or "",
            "areas": result.get("areas") or [],
            "budget_max": result.get("budget_max"),
            "property_type": result.get("property_type"),
            "furnishing": result.get("furnishing"),
            "preferences": result.get("preferences"),
        }
    except Exception:
        return {**_FALLBACK}
