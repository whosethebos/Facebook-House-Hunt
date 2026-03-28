# backend/tests/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch
from llm.parse_criteria import parse_criteria
from llm.analyze import analyze_post

# --- parse_criteria tests ---

async def test_parse_criteria_extracts_fields():
    mock_response = {
        "city": "Pune",
        "areas": ["Hinjewadi"],
        "budget_max": 15000,
        "property_type": "1BHK",
        "furnishing": "furnished",
        "preferences": "no brokerage",
    }
    with patch("llm.parse_criteria.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await parse_criteria("Looking for furnished 1BHK in Pune near Hinjewadi, budget 15k, no brokerage")
    assert result["city"] == "Pune"
    assert result["areas"] == ["Hinjewadi"]
    assert result["budget_max"] == 15000
    assert result["property_type"] == "1BHK"
    assert result["furnishing"] == "furnished"


async def test_parse_criteria_handles_missing_fields():
    mock_response = {"city": "Mumbai", "areas": [], "budget_max": None,
                     "property_type": None, "furnishing": None, "preferences": None}
    with patch("llm.parse_criteria.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await parse_criteria("Looking for a place in Mumbai")
    assert result["city"] == "Mumbai"
    assert result["areas"] == []
    assert result["budget_max"] is None


# --- analyze_post tests ---

async def test_analyze_post_returns_score():
    mock_response = {
        "extracted_rent": 14500,
        "extracted_area": "Hinjewadi Phase 2",
        "extracted_type": "1BHK",
        "extracted_furnishing": "furnished",
        "scores": {"area": 28, "budget": 24, "type": 18, "furnishing": 12, "preferences": 8},
        "total_score": 90,
        "summary": "Furnished 1BHK in Hinjewadi Phase 2",
    }
    with patch("llm.analyze.chat_json", new=AsyncMock(return_value=mock_response)):
        result = await analyze_post(
            post_text="1BHK available in Hinjewadi Phase 2, fully furnished, ₹14,500/mo",
            city="Pune",
            areas=["Hinjewadi"],
            budget_max=15000,
            property_type="1BHK",
            furnishing="furnished",
            preferences="no brokerage",
        )
    assert result["match_score"] == 90
    assert result["extracted_rent"] == 14500
    assert result["score_breakdown"]["area"] == 28


async def test_analyze_post_returns_fallback_on_error():
    with patch("llm.analyze.chat_json", side_effect=Exception("Ollama unreachable")):
        result = await analyze_post(
            post_text="some post",
            city="Pune", areas=[], budget_max=None,
            property_type=None, furnishing=None, preferences=None,
        )
    assert result["match_score"] == 0
    assert result["summary"] == ""
