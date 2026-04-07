from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Playwright

from app.config import settings
from app.markdown import clean_html
from app.models import ScrapeRequest, ScrapeResult, PageMetadata

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_semaphore: Optional[asyncio.Semaphore] = None

_JS_MARKERS = re.compile(
    r'(id=["\']root["\']|id=["\']app["\']|__NEXT_DATA__|__nuxt__|<noscript>)',
    re.IGNORECASE,
)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def start_browser() -> None:
    global _playwright, _browser, _semaphore
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    _semaphore = asyncio.Semaphore(settings.max_concurrency)


async def stop_browser() -> None:
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()


def _extract_metadata(html: str, url: str, status_code: int) -> PageMetadata:
    soup = BeautifulSoup(html, "html.parser")

    def meta(name: str) -> Optional[str]:
        el = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        return el.get("content") if el else None

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    return PageMetadata(
        title=title or meta("og:title"),
        description=meta("description") or meta("og:description"),
        ogImage=meta("og:image"),
        url=url,
        statusCode=status_code,
    )


def _needs_js(html: str) -> bool:
    body_text = BeautifulSoup(html, "html.parser").get_text(strip=True)
    if len(body_text) < 200:
        return True
    return bool(_JS_MARKERS.search(html))


async def _fetch_with_httpx(url: str, timeout: int) -> tuple[str, int]:
    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS,
        follow_redirects=True,
        timeout=timeout / 1000,
        verify="/etc/ssl/certs/ca-certificates.crt",
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text, resp.status_code


async def _fetch_with_playwright(url: str, wait_for: int, timeout: int) -> tuple[str, int]:
    assert _browser is not None and _semaphore is not None
    async with _semaphore:
        context = await _browser.new_context(extra_http_headers=_BROWSER_HEADERS)
        page = await context.new_page()
        try:
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=timeout,
            )
            if wait_for > 0:
                await page.wait_for_timeout(wait_for)
            html = await page.content()
            status = response.status if response else 200
        finally:
            await context.close()
    return html, status


async def scrape(request: ScrapeRequest) -> ScrapeResult:
    url = request.url
    timeout = request.timeout

    try:
        html, status = await _fetch_with_httpx(url, timeout)
    except Exception:
        html, status = "", 0

    use_playwright = request.waitFor > 0 or not html or _needs_js(html)

    if use_playwright:
        html, status = await _fetch_with_playwright(url, request.waitFor, timeout)

    metadata = _extract_metadata(html, url, status)
    cleaned_html, md = clean_html(html, request.onlyMainContent)

    return ScrapeResult(
        markdown=md if "markdown" in request.formats else None,
        html=cleaned_html if "html" in request.formats else None,
        metadata=metadata,
    )
