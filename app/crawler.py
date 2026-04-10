from __future__ import annotations

import contextlib
import json
import logging
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from celery import Celery

logger = logging.getLogger(__name__)

from app.config import settings
from app.models import CrawlRequest, ScrapeResult

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


def _fetch_url_with_retry(client: "httpx.Client", url: str) -> tuple[str, int]:
    import httpx
    last_exc: Exception | None = None
    for attempt in range(settings.scrape_max_retries + 1):
        try:
            resp = client.get(url)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < settings.scrape_max_retries:
                    delay = settings.scrape_retry_backoff * (2 ** attempt)
                    if resp.status_code == 429:
                        with contextlib.suppress(Exception):
                            delay = float(resp.headers.get("Retry-After", delay))
                    logger.warning(
                        "Retrying %s (status %d) in %.1fs (attempt %d/%d)",
                        url, resp.status_code, delay, attempt + 1, settings.scrape_max_retries,
                    )
                    time.sleep(delay)
                    continue
            resp.raise_for_status()
            return resp.text, resp.status_code
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < settings.scrape_max_retries:
                delay = settings.scrape_retry_backoff * (2 ** attempt)
                logger.warning(
                    "Retrying %s (transport error: %s) in %.1fs (attempt %d/%d)",
                    url, exc, delay, attempt + 1, settings.scrape_max_retries,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


@celery_app.task(name="crawl_site", bind=True)
def crawl_site(self, job_id: str, crawl_request_dict: dict) -> None:
    import redis as redis_lib
    import httpx
    from app.markdown import clean_html
    from app.scraper import _extract_metadata, _BROWSER_HEADERS

    r = redis_lib.from_url(settings.redis_url)
    request = CrawlRequest(**crawl_request_dict)

    job_key = f"crawl:{job_id}"
    results_key = f"crawl:{job_id}:results"

    r.hset(job_key, mapping={"status": "scraping", "total": 0, "completed": 0})

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(request.url, 0)]  # (url, depth)
    total = 0
    completed = 0

    with httpx.Client(
        headers=_BROWSER_HEADERS,
        follow_redirects=True,
        timeout=request.scrapeOptions.timeout / 1000,
        verify="/etc/ssl/certs/ca-certificates.crt",
    ) as client:
        # robots.txt cache: domain_url → RobotFileParser
        robots_cache: dict[str, RobotFileParser] = {}

        def _get_robots(domain_url: str) -> RobotFileParser:
            if domain_url not in robots_cache:
                rfp = RobotFileParser()
                try:
                    resp = client.get(
                        f"{domain_url}/robots.txt",
                        follow_redirects=True,
                        timeout=10,
                    )
                    rfp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
                except Exception:
                    rfp.parse([])  # can't reach robots.txt → treat as allow-all
                robots_cache[domain_url] = rfp
            return robots_cache[domain_url]

        while queue and total < request.limit:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if settings.crawl_respect_robots:
                parsed_url = urlparse(url)
                domain_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                if not _get_robots(domain_url).can_fetch("*", url):
                    logger.info("robots.txt disallows %s, skipping", url)
                    continue

            total += 1
            r.hset(job_key, "total", total)

            try:
                html, status = _fetch_url_with_retry(client, url)
            except Exception as exc:
                logger.error("Failed to fetch %s: %s: %s", url, type(exc).__name__, exc)
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
