from __future__ import annotations

import asyncio
import json
import uuid
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from celery import Celery

from app.config import settings
from app.models import CrawlRequest, ScrapeRequest, ScrapeResult

celery_app = Celery("crawler", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


def _same_origin(base: str, href: str) -> bool:
    base_parsed = urlparse(base)
    href_parsed = urlparse(href)
    return (
        href_parsed.scheme in ("http", "https")
        and href_parsed.netloc == base_parsed.netloc
    )


def _is_backward_link(base_url: str, href: str, origin: str) -> bool:
    """Return True if href would navigate above the origin path depth."""
    origin_path = urlparse(origin).path.rstrip("/")
    href_path = urlparse(href).path.rstrip("/")
    return not href_path.startswith(origin_path)


def _extract_links(html: str, current_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].split("#")[0].strip()
        if not href:
            continue
        absolute = urljoin(current_url, href)
        if _same_origin(current_url, absolute):
            links.append(absolute)
    return links


@celery_app.task(name="crawl_site", bind=True)
def crawl_site(self, job_id: str, crawl_request_dict: dict) -> None:
    import redis as redis_lib

    r = redis_lib.from_url(settings.redis_url)
    request = CrawlRequest(**crawl_request_dict)

    job_key = f"crawl:{job_id}"
    results_key = f"crawl:{job_id}:results"

    r.hset(job_key, mapping={"status": "scraping", "total": 0, "completed": 0})

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(request.url, 0)]  # (url, depth)
    total = 0
    completed = 0

    # We need a sync scrape path for Celery — use httpx sync + html parsing
    # (Playwright in a Celery worker is complex; use httpx-only for crawl)
    import httpx
    from app.markdown import clean_html
    from app.scraper import _extract_metadata, _BROWSER_HEADERS

    while queue and total < request.limit:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        total += 1
        r.hset(job_key, "total", total)

        try:
            with httpx.Client(
                headers=_BROWSER_HEADERS,
                follow_redirects=True,
                timeout=request.scrapeOptions.timeout / 1000,
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                html = resp.text
                status = resp.status_code
        except Exception as exc:
            r.rpush(
                results_key,
                json.dumps(
                    {
                        "markdown": None,
                        "html": None,
                        "metadata": {
                            "url": url,
                            "statusCode": 0,
                            "title": None,
                            "description": None,
                            "ogImage": None,
                            "error": str(exc),
                        },
                    }
                ),
            )
            completed += 1
            r.hset(job_key, "completed", completed)
            continue

        metadata = _extract_metadata(html, url, status)
        cleaned_html, md = clean_html(html, request.scrapeOptions.onlyMainContent)

        result = ScrapeResult(
            markdown=md if "markdown" in request.scrapeOptions.formats else None,
            html=cleaned_html if "html" in request.scrapeOptions.formats else None,
            metadata=metadata,
        )
        r.rpush(results_key, result.model_dump_json())

        completed += 1
        r.hset(job_key, "completed", completed)

        if depth < request.maxDepth:
            links = _extract_links(html, url)
            for link in links:
                if link not in visited:
                    if not request.allowBackwardLinks and _is_backward_link(
                        url, link, request.url
                    ):
                        continue
                    queue.append((link, depth + 1))

    r.hset(job_key, "status", "completed")
    r.expire(job_key, 3600)
    r.expire(results_key, 3600)
