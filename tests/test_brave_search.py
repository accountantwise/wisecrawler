import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.brave_search import query


@pytest.fixture
def mock_brave(monkeypatch):
    """Fixture that mocks httpx.AsyncClient and settings with a valid API key."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"web": {"results": []}}

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr("app.brave_search.httpx.AsyncClient", mock_cls)
    monkeypatch.setattr("app.brave_search.settings", MagicMock(brave_api_key="test-key"))

    return mock_response, mock_http_client


async def test_query_success(mock_brave):
    mock_response, _ = mock_brave
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "T1", "url": "https://a.com", "description": "S1"},
                {"title": "T2", "url": "https://b.com", "description": "S2"},
                {"title": "T3", "url": "https://c.com", "description": "S3"},
            ]
        }
    }

    results = await query("fashion week", count=3)

    assert len(results) == 3
    assert results[0] == {"title": "T1", "url": "https://a.com", "snippet": "S1"}
    assert results[1]["snippet"] == "S2"
    assert results[2]["url"] == "https://c.com"


async def test_query_empty_results(mock_brave):
    mock_response, _ = mock_brave
    mock_response.json.return_value = {"web": {"results": []}}

    results = await query("unlikely query xyz123", count=5)

    assert results == []


async def test_query_missing_web_key(mock_brave):
    mock_response, _ = mock_brave
    mock_response.json.return_value = {}

    results = await query("test")

    assert results == []


async def test_query_brave_429(mock_brave):
    _, mock_http_client = mock_brave
    mock_http_client.get.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(spec=httpx.Request),
        response=MagicMock(status_code=429),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await query("test")


async def test_query_brave_500(mock_brave):
    _, mock_http_client = mock_brave
    mock_http_client.get.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(spec=httpx.Request),
        response=MagicMock(status_code=500),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await query("test")


async def test_query_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.brave_search.settings", MagicMock(brave_api_key=""))

    with pytest.raises(ValueError, match="BRAVE_API_KEY is not configured"):
        await query("test")
