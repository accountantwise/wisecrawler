from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    url: str
    formats: list[Literal["markdown", "html"]] = ["markdown"]
    onlyMainContent: bool = True
    waitFor: int = 0
    timeout: int = 30000


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


class CrawlJobStarted(BaseModel):
    id: str
    url: str


class CrawlStatus(BaseModel):
    status: Literal["scraping", "completed", "failed", "cancelled"]
    total: int
    completed: int
    creditsUsed: int
    data: list[ScrapeResult]
