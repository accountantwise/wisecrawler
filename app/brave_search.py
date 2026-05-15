from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _get_api_key() -> str:
    key = settings.brave_api_key
    if not key:
        raise ValueError("BRAVE_API_KEY is not configured")
    return key


async def query(q: str, count: int = 10) -> list[dict]:
    """Query Brave Search and return [{title, url, snippet}, ...]."""
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": _get_api_key(),
    }
    params = {"q": q, "count": count}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

    web_results = (data.get("web") or {}).get("results") or []
    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in web_results
    ]
    logger.info("Brave search: query_len=%d results=%d", len(q), len(results))
    return results
