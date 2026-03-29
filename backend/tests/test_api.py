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
