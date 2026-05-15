import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.config import settings


@pytest.fixture
def client():
    """TestClient with Playwright lifespan mocked out (no browser needed for these tests)."""
    with patch("app.main.start_browser", new_callable=AsyncMock), \
         patch("app.main.stop_browser", new_callable=AsyncMock):
        with TestClient(app) as c:
            yield c


def get_headers():
    """Return authorization headers with the API key if configured."""
    if settings.api_key:
        return {"Authorization": f"Bearer {settings.api_key}"}
    return {}


def test_search_success(client):
    with patch("app.brave_search.query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {"title": "T1", "url": "https://a.com", "snippet": "S1"},
            {"title": "T2", "url": "https://b.com", "snippet": "S2"},
        ]
        response = client.post("/v1/search", json={"query": "louis vuitton"}, headers=get_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["title"] == "T1"
    assert body["results"][1]["snippet"] == "S2"


def test_search_empty_query(client):
    response = client.post("/v1/search", json={"query": "   "}, headers=get_headers())

    assert response.status_code == 400
    assert "must not be empty" in response.json()["detail"]


def test_search_count_out_of_range(client):
    response = client.post("/v1/search", json={"query": "test", "count": 50}, headers=get_headers())

    assert response.status_code == 422


def test_search_missing_api_key(client):
    with patch("app.brave_search.query", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = ValueError("BRAVE_API_KEY is not configured")
        response = client.post("/v1/search", json={"query": "test"}, headers=get_headers())

    assert response.status_code == 503
    assert "BRAVE_API_KEY" in response.json()["detail"]


def test_search_brave_429(client):
    exc = httpx.HTTPStatusError(
        "429",
        request=MagicMock(spec=httpx.Request),
        response=MagicMock(status_code=429),
    )
    with patch("app.brave_search.query", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = exc
        response = client.post("/v1/search", json={"query": "test"}, headers=get_headers())

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_search_brave_5xx(client):
    exc = httpx.HTTPStatusError(
        "500",
        request=MagicMock(spec=httpx.Request),
        response=MagicMock(status_code=500),
    )
    with patch("app.brave_search.query", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = exc
        response = client.post("/v1/search", json={"query": "test"}, headers=get_headers())

    assert response.status_code == 502
    assert "upstream" in response.json()["detail"].lower()


def test_search_network_failure(client):
    with patch("app.brave_search.query", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = httpx.ConnectError("Connection refused")
        response = client.post("/v1/search", json={"query": "test"}, headers=get_headers())

    assert response.status_code == 502
    assert "upstream" in response.json()["detail"].lower()
