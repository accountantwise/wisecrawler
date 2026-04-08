# WiseCrawler - A Firecrawl Clone

A self-hosted web scraping and crawling API that converts any website into clean, LLM-ready markdown. Optionally passes scraped or crawled content to an AI model for analysis or summarization — with support for OpenAI, Anthropic, Gemini, and OpenRouter.

## Features

- **Single-page scraping** — httpx for speed, automatic Playwright fallback for JS-heavy sites
- **Async site crawling** — BFS crawl with configurable depth, page limit, and link filtering
- **AI analysis** — send scraped or crawled content to an AI model with a custom prompt
- **AI summarization** — one-shot summarize any URL with no prompt required
- **Multi-provider AI** — OpenAI, Anthropic, Gemini, or OpenRouter; configured via env vars
- **Token-safe aggregation** — automatically stays within model context windows when analyzing multi-page crawls
- **Optional API key auth** — bearer token protection for all endpoints

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (v2)
- An API key for at least one AI provider if you want to use the AI endpoints

## Quick Start

**1. Clone the repo**

```bash
git clone <repo-url>
cd firecrawl_clone
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and fill in the values you need (see [Configuration](#configuration) below).

**3. Build and run**

```bash
docker compose up --build
```

The API is available at `http://localhost:3002`.

**4. Verify**

```bash
curl http://localhost:3002/health
# {"status":"ok"}
```

## Configuration

All settings are read from environment variables (or a `.env` file in the project root).

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3002` | Port the API listens on |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Playwright navigation timeout (ms) |
| `MAX_CONCURRENCY` | `5` | Max simultaneous Playwright pages |
| `API_KEY` | _(empty)_ | Bearer token for all endpoints. Leave empty to disable auth. |

### AI

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `openai` | Which AI backend to use: `openai`, `anthropic`, `gemini`, or `openrouter` |
| `AI_MODEL` | _(empty)_ | Model name. Leave empty to use the provider's default (see table below). |
| `OPENAI_API_KEY` | _(empty)_ | Required when `AI_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required when `AI_PROVIDER=anthropic` |
| `GEMINI_API_KEY` | _(empty)_ | Required when `AI_PROVIDER=gemini` |
| `OPENROUTER_API_KEY` | _(empty)_ | Required when `AI_PROVIDER=openrouter` |
| `AI_MAX_TOKENS_INPUT` | `100000` | Character ceiling applied per page before token counting (crawl/analyze) |
| `AI_MAX_PAGES` | `50` | Maximum pages aggregated when analyzing a crawl job |
| `AI_SUMMARIZE_PROMPT` | _(built-in)_ | System prompt used by `/v1/scrape/summarize`. Override to customize. |

### Provider defaults

When `AI_MODEL` is empty, the following model is used:

| Provider | Default model |
|----------|--------------|
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-3-5-haiku-20241022` |
| `gemini` | `gemini-1.5-flash` |
| `openrouter` | `openai/gpt-4o-mini` |

## API Reference

### Health check

```
GET /health
```

```bash
curl http://localhost:3002/health
```

---

### Scrape a URL

```
POST /v1/scrape
```

Fetches a single page and returns clean markdown and/or HTML.

**Request body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | URL to scrape |
| `formats` | string[] | `["markdown"]` | Output formats: `"markdown"`, `"html"`, or both |
| `onlyMainContent` | bool | `true` | Strip nav, footer, ads; extract main content |
| `waitFor` | int | `0` | Extra wait time after page load (ms). Forces Playwright. |
| `timeout` | int | `30000` | Request timeout (ms) |

```bash
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

**Response**

```json
{
  "success": true,
  "data": {
    "markdown": "# Example Domain\n\nThis domain is for use...",
    "html": null,
    "metadata": {
      "title": "Example Domain",
      "description": null,
      "ogImage": null,
      "url": "https://example.com",
      "statusCode": 200
    }
  }
}
```

---

### Scrape + AI analysis

```
POST /v1/scrape/analyze
```

Scrapes a URL and passes the markdown to an AI model with your prompt.

**Request body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | URL to scrape |
| `prompt` | string | required | Instruction for the AI model |
| `onlyMainContent` | bool | `true` | Extract main content only |
| `waitFor` | int | `0` | Extra wait (ms), forces Playwright |
| `timeout` | int | `30000` | Request timeout (ms) |

```bash
curl -X POST http://localhost:3002/v1/scrape/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","prompt":"What is this site about? List the key points."}'
```

**Response**

```json
{
  "success": true,
  "url": "https://example.com",
  "analysis": "This site is a placeholder domain used for illustrative examples...",
  "markdown": "# Example Domain\n\n...",
  "provider": "openai",
  "model": "gpt-4o-mini"
}
```

---

### Scrape + AI summarization

```
POST /v1/scrape/summarize
```

Scrapes a URL and returns a summary using the built-in summarization prompt (override via `AI_SUMMARIZE_PROMPT`).

**Request body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | URL to scrape |
| `onlyMainContent` | bool | `true` | Extract main content only |
| `waitFor` | int | `0` | Extra wait (ms), forces Playwright |
| `timeout` | int | `30000` | Request timeout (ms) |

```bash
curl -X POST http://localhost:3002/v1/scrape/summarize \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

**Response**

```json
{
  "success": true,
  "url": "https://example.com",
  "summary": "Example.com is a placeholder domain maintained by IANA...",
  "provider": "anthropic",
  "model": "claude-3-5-haiku-20241022"
}
```

---

### Start a crawl

```
POST /v1/crawl
```

Starts an async BFS crawl from a seed URL. Returns a job ID to poll.

**Request body**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | Seed URL |
| `maxDepth` | int | `2` | Maximum link depth from seed |
| `limit` | int | `100` | Maximum pages to crawl |
| `allowBackwardLinks` | bool | `false` | Allow links that go up the URL path |
| `scrapeOptions.formats` | string[] | `["markdown"]` | Formats to store per page |
| `scrapeOptions.onlyMainContent` | bool | `true` | Extract main content only |

```bash
curl -X POST http://localhost:3002/v1/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","limit":10,"maxDepth":2}'
```

**Response**

```json
{"id": "a1b2c3d4-...", "url": "https://example.com"}
```

---

### Poll crawl status

```
GET /v1/crawl/{id}
```

```bash
curl http://localhost:3002/v1/crawl/a1b2c3d4-...
```

**Response**

```json
{
  "status": "completed",
  "total": 5,
  "completed": 5,
  "creditsUsed": 5,
  "data": [
    {
      "markdown": "...",
      "html": null,
      "metadata": {"url": "https://example.com", "statusCode": 200, ...}
    }
  ]
}
```

Status values: `scraping` | `completed` | `failed` | `cancelled`

---

### Cancel a crawl

```
DELETE /v1/crawl/{id}
```

```bash
curl -X DELETE http://localhost:3002/v1/crawl/a1b2c3d4-...
```

---

### AI analysis of a crawl

```
POST /v1/crawl/analyze
```

Passes all markdown from a **completed** crawl job to an AI model with your prompt. Content is automatically truncated to fit within the model's context window (80K token budget). The response tells you how many pages were included and whether truncation occurred.

**Request body**

| Field | Type | Description |
|-------|------|-------------|
| `crawl_id` | string | ID of a completed crawl job |
| `prompt` | string | Instruction for the AI model |

```bash
curl -X POST http://localhost:3002/v1/crawl/analyze \
  -H 'Content-Type: application/json' \
  -d '{"crawl_id":"a1b2c3d4-...","prompt":"What topics does this site cover? List them."}'
```

**Response**

```json
{
  "success": true,
  "crawl_id": "a1b2c3d4-...",
  "pages_analyzed": 5,
  "was_truncated": false,
  "analysis": "The site covers the following topics: ...",
  "provider": "openai",
  "model": "gpt-4o-mini"
}
```

> **Note:** `POST /v1/crawl/analyze` requires the crawl to be in `completed` status. Poll `GET /v1/crawl/{id}` until `status == "completed"` before calling this endpoint.

---

## Authentication

Set `API_KEY` in your `.env` to enable bearer token auth on all endpoints:

```bash
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Authorization: Bearer your-secret-key' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'
```

Leave `API_KEY` empty (the default) to disable authentication.

## Architecture

```
┌─────────┐     HTTP      ┌─────────────────────────────┐
│  Client │ ────────────► │  api  (FastAPI + uvicorn)   │
└─────────┘               │  - /v1/scrape  (sync)        │
                          │  - /v1/scrape/analyze (sync) │
                          │  - /v1/scrape/summarize      │
                          │  - /v1/crawl  (enqueue)      │
                          │  - /v1/crawl/analyze (sync)  │
                          └────────────┬────────────────-┘
                                       │ Celery task
                          ┌────────────▼────────────────┐
                          │  worker  (Celery)            │
                          │  - BFS crawl via httpx       │
                          │  - stores results in Redis   │
                          └────────────┬────────────────-┘
                                       │
                          ┌────────────▼────────────────┐
                          │  redis  (queue + results)   │
                          └─────────────────────────────┘
```

Crawl results expire from Redis after **1 hour**.

## Development

Rebuild after code changes:

```bash
docker compose up --build
```

Follow live logs:

```bash
docker compose logs -f api
docker compose logs -f worker
```
