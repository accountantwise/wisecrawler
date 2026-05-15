from __future__ import annotations

import json
import logging
import traceback
import uuid
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Optional

logging.basicConfig(level=logging.INFO)

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import brave_search
from app.ai_client import AIClientError, _PROVIDER_DEFAULTS, complete as ai_complete
from app.config import settings
from app.crawler import crawl_site
from app.models import (
    CrawlAnalyzeRequest,
    CrawlAnalyzeResponse,
    CrawlJobStarted,
    CrawlRequest,
    CrawlStatus,
    ScrapeAnalyzeRequest,
    ScrapeAnalyzeResponse,
    ScrapeSummarizeRequest,
    ScrapeSummarizeResponse,
    ScrapeRequest,
    ScrapeResponse,
    ScrapeResult,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.scraper import scrape, start_browser, stop_browser
from app.token_utils import aggregate_pages

_redis: Optional[aioredis.Redis] = None

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    await start_browser()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    await stop_browser()
    await _redis.aclose()


app = FastAPI(title="WiseCrawler", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _check_api_key(request: Request) -> None:
    if not settings.api_key:
        return
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not compare_digest(token, settings.api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/scrape", response_model=ScrapeResponse)
@limiter.limit("30/minute")
async def scrape_url(body: ScrapeRequest, request: Request):
    _check_api_key(request)
    try:
        result = await scrape(body)
    except Exception as exc:
        logging.error("Scrape failed for %s:\n%s", body.url, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to scrape URL")
    return ScrapeResponse(success=True, data=result)


@app.post("/v1/scrape/analyze", response_model=ScrapeAnalyzeResponse)
@limiter.limit("10/minute")
async def scrape_and_analyze(body: ScrapeAnalyzeRequest, request: Request):
    _check_api_key(request)
    scrape_req = ScrapeRequest(
        url=body.url,
        formats=["markdown"],
        onlyMainContent=body.onlyMainContent,
        waitFor=body.waitFor,
        timeout=body.timeout,
    )
    try:
        result = await scrape(scrape_req)
    except Exception as exc:
        logging.error("Scrape failed for %s:\n%s", body.url, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to scrape URL")

    content = result.markdown or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="No markdown content extracted")

    try:
        analysis = await ai_complete(body.prompt, content)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    provider = settings.ai_provider
    return ScrapeAnalyzeResponse(
        success=True,
        url=body.url,
        analysis=analysis,
        markdown=content,
        provider=provider,
        model=settings.ai_model or _PROVIDER_DEFAULTS[provider],
    )


@app.post("/v1/scrape/summarize", response_model=ScrapeSummarizeResponse)
@limiter.limit("10/minute")
async def scrape_and_summarize(body: ScrapeSummarizeRequest, request: Request):
    _check_api_key(request)
    scrape_req = ScrapeRequest(
        url=body.url,
        formats=["markdown"],
        onlyMainContent=body.onlyMainContent,
        waitFor=body.waitFor,
        timeout=body.timeout,
    )
    try:
        result = await scrape(scrape_req)
    except Exception as exc:
        logging.error("Scrape failed for %s:\n%s", body.url, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to scrape URL")

    content = result.markdown or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="No markdown content extracted")

    try:
        summary = await ai_complete(settings.ai_summarize_prompt, content)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    provider = settings.ai_provider
    return ScrapeSummarizeResponse(
        success=True,
        url=body.url,
        summary=summary,
        provider=provider,
        model=settings.ai_model or _PROVIDER_DEFAULTS[provider],
    )


@app.post("/v1/search", response_model=SearchResponse)
@limiter.limit("20/minute")
async def search(body: SearchRequest, request: Request):
    _check_api_key(request)
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        results = await brave_search.query(q, count=body.count)
    except ValueError as e:
        logging.warning("Search: missing API key")
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            logging.warning("Search: Brave rate limit hit")
            raise HTTPException(status_code=429, detail="Search rate limit reached")
        logging.warning("Search: Brave returned %d", status)
        raise HTTPException(status_code=502, detail="Upstream search service failed")
    except httpx.HTTPError as e:
        logging.warning("Search: network error reaching Brave: %s", type(e).__name__)
        raise HTTPException(status_code=502, detail="Upstream search service failed")
    return SearchResponse(results=[SearchResult(**r) for r in results])


@app.post("/v1/crawl/analyze", response_model=CrawlAnalyzeResponse)
@limiter.limit("10/minute")
async def analyze_crawl(body: CrawlAnalyzeRequest, request: Request):
    _check_api_key(request)
    job_key = f"crawl:{body.crawl_id}"
    results_key = f"crawl:{body.crawl_id}:results"

    job = await _redis.hgetall(job_key)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail=f"Crawl not yet complete: {job.get('status')}")

    raw_results = await _redis.lrange(results_key, 0, -1)
    markdowns = [
        ScrapeResult(**json.loads(r)).markdown or ""
        for r in raw_results
    ]
    markdowns = [m for m in markdowns if m.strip()]
    if not markdowns:
        raise HTTPException(status_code=422, detail="No usable markdown found in crawl results")

    combined, pages_included, was_truncated = aggregate_pages(
        markdowns,
        per_page_char_limit=settings.ai_max_tokens_input,
        max_pages=settings.ai_max_pages,
    )

    try:
        analysis = await ai_complete(body.prompt, combined)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    provider = settings.ai_provider
    return CrawlAnalyzeResponse(
        success=True,
        crawl_id=body.crawl_id,
        pages_analyzed=pages_included,
        was_truncated=was_truncated,
        analysis=analysis,
        provider=provider,
        model=settings.ai_model or _PROVIDER_DEFAULTS[provider],
    )


@app.post("/v1/crawl", response_model=CrawlJobStarted)
@limiter.limit("10/minute")
async def start_crawl(body: CrawlRequest, request: Request):
    _check_api_key(request)
    job_id = str(uuid.uuid4())
    crawl_site.apply_async(args=[job_id, body.model_dump()], task_id=job_id)
    return CrawlJobStarted(id=job_id, url=body.url)


@app.get("/v1/crawl/{job_id}", response_model=CrawlStatus)
@limiter.limit("60/minute")
async def get_crawl(job_id: str, request: Request):
    _check_api_key(request)
    job_key = f"crawl:{job_id}"
    results_key = f"crawl:{job_id}:results"

    job = await _redis.hgetall(job_key)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    raw_results = await _redis.lrange(results_key, 0, -1)
    results = [ScrapeResult(**json.loads(r)) for r in raw_results]

    return CrawlStatus(
        status=job.get("status", "scraping"),
        total=int(job.get("total", 0)),
        completed=int(job.get("completed", 0)),
        creditsUsed=len(results),
        data=results,
    )


@app.delete("/v1/crawl/{job_id}")
@limiter.limit("10/minute")
async def cancel_crawl(job_id: str, request: Request):
    _check_api_key(request)
    from app.crawler import celery_app

    celery_app.control.revoke(job_id, terminate=True)
    job_key = f"crawl:{job_id}"
    await _redis.hset(job_key, "status", "cancelled")
    return {"success": True, "id": job_id}
