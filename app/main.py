from __future__ import annotations

import json
import logging
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Optional

logging.basicConfig(level=logging.INFO)

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.crawler import crawl_site
from app.models import (
    CrawlJobStarted,
    CrawlRequest,
    CrawlStatus,
    ScrapeRequest,
    ScrapeResponse,
    ScrapeResult,
)
from app.scraper import scrape, start_browser, stop_browser

_redis: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    await start_browser()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield
    await stop_browser()
    await _redis.aclose()


app = FastAPI(title="Firecrawl Clone", version="1.0.0", lifespan=lifespan)


def _check_api_key(request: Request) -> None:
    if not settings.api_key:
        return
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/scrape", response_model=ScrapeResponse)
async def scrape_url(body: ScrapeRequest, request: Request):
    _check_api_key(request)
    try:
        result = await scrape(body)
    except Exception as exc:
        logging.error("Scrape failed for %s:\n%s", body.url, traceback.format_exc())
        raise HTTPException(status_code=500, detail=traceback.format_exc())
    return ScrapeResponse(success=True, data=result)


@app.post("/v1/crawl", response_model=CrawlJobStarted)
async def start_crawl(body: CrawlRequest, request: Request):
    _check_api_key(request)
    job_id = str(uuid.uuid4())
    crawl_site.apply_async(args=[job_id, body.model_dump()], task_id=job_id)
    return CrawlJobStarted(id=job_id, url=body.url)


@app.get("/v1/crawl/{job_id}", response_model=CrawlStatus)
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
async def cancel_crawl(job_id: str, request: Request):
    _check_api_key(request)
    from app.crawler import celery_app

    celery_app.control.revoke(job_id, terminate=True)
    job_key = f"crawl:{job_id}"
    await _redis.hset(job_key, "status", "cancelled")
    return {"success": True, "id": job_id}
