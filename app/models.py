from __future__ import annotations

import ipaddress
import socket
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


def _reject_internal_url(url: str) -> str:
    """Raise ValueError if the URL resolves to a private/loopback address."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname")
    # Block obvious internal hostnames
    if hostname.lower() in ("localhost",):
        raise ValueError("Requests to internal hosts are not allowed")
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Requests to internal/private IP addresses are not allowed")
    except ValueError as exc:
        # Not a raw IP — it's a hostname; re-raise only our own errors
        if "Requests to" in str(exc):
            raise
    return url


class ScrapeRequest(BaseModel):
    url: str
    formats: list[Literal["markdown", "html"]] = ["markdown"]
    onlyMainContent: bool = True
    waitFor: int = 0
    timeout: int = 30000

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _reject_internal_url(v)


class PageMetadata(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    ogImage: Optional[str] = None
    url: str
    statusCode: int


class ScrapeResult(BaseModel):
    markdown: Optional[str] = None
    html: Optional[str] = None
    metadata: PageMetadata


class ScrapeResponse(BaseModel):
    success: bool
    data: ScrapeResult


class ScrapeOptions(BaseModel):
    formats: list[Literal["markdown", "html"]] = ["markdown"]
    onlyMainContent: bool = True
    waitFor: int = 0
    timeout: int = 30000


class CrawlRequest(BaseModel):
    url: str
    maxDepth: int = 2
    limit: int = 100
    allowBackwardLinks: bool = False
    scrapeOptions: ScrapeOptions = ScrapeOptions()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _reject_internal_url(v)


class CrawlJobStarted(BaseModel):
    id: str
    url: str


class CrawlStatus(BaseModel):
    status: Literal["scraping", "completed", "failed", "cancelled"]
    total: int
    completed: int
    creditsUsed: int
    data: list[ScrapeResult]


class ScrapeAnalyzeRequest(BaseModel):
    url: str
    prompt: str
    onlyMainContent: bool = True
    waitFor: int = 0
    timeout: int = 30000

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _reject_internal_url(v)


class ScrapeAnalyzeResponse(BaseModel):
    success: bool
    url: str
    analysis: str
    markdown: Optional[str] = None
    provider: str
    model: str


class ScrapeSummarizeRequest(BaseModel):
    url: str
    onlyMainContent: bool = True
    waitFor: int = 0
    timeout: int = 30000

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _reject_internal_url(v)


class ScrapeSummarizeResponse(BaseModel):
    success: bool
    url: str
    summary: str
    provider: str
    model: str


class CrawlAnalyzeRequest(BaseModel):
    crawl_id: str
    prompt: str


class CrawlAnalyzeResponse(BaseModel):
    success: bool
    crawl_id: str
    pages_analyzed: int
    was_truncated: bool
    analysis: str
    provider: str
    model: str


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchRequest(BaseModel):
    query: str
    count: int = Field(default=10, ge=1, le=20)


class SearchResponse(BaseModel):
    results: list[SearchResult]
