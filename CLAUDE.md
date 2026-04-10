# WiseCrawler

## Project Overview
A clone of Firecrawl — a web scraping and crawling API that converts websites into clean, LLM-ready markdown. Also supports AI-powered analysis and summarization of scraped/crawled content via OpenAI, Anthropic, Gemini, or OpenRouter.

## Dev Commands

```bash
# Build and start all services
docker compose up --build

# Start in background
docker compose up -d --build

# View logs
docker compose logs -f api
docker compose logs -f worker

# Stop everything
docker compose down
```

### Smoke tests
```bash
# Health check
curl http://localhost:3002/health

# Scrape a single URL
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'

# Scrape a JS-heavy site (triggers Playwright)
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://react.dev","waitFor":2000}'

# Scrape + analyze with AI
curl -X POST http://localhost:3002/v1/scrape/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","prompt":"What is this site about?"}'

# Scrape + summarize with AI (uses default summarize prompt)
curl -X POST http://localhost:3002/v1/scrape/summarize \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}'

# Start a crawl job
curl -X POST http://localhost:3002/v1/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","limit":5}'

# Poll crawl status (replace <id> with the returned job ID)
curl http://localhost:3002/v1/crawl/<id>

# Analyze all pages from a completed crawl with AI
curl -X POST http://localhost:3002/v1/crawl/analyze \
  -H 'Content-Type: application/json' \
  -d '{"crawl_id":"<id>","prompt":"Summarize all pages found"}'
```

## Architecture

Three Docker services:
- **redis** — job queue + result store (redis:7-alpine)
- **api** — FastAPI + uvicorn, handles `/v1/scrape` synchronously and `/v1/crawl` async; also runs AI analysis/summarization endpoints
- **worker** — Celery worker, executes crawl jobs from the queue (httpx only, no Playwright)

```
app/
  config.py       # Settings via pydantic-settings / env vars
  models.py       # Pydantic v2 request/response schemas
  scraper.py      # fetch URL → clean markdown (httpx first, Playwright fallback)
  crawler.py      # Celery task: BFS crawl + link discovery
  markdown.py     # HTML cleaning (BS4) + html→markdown (markdownify)
  ai_client.py    # Provider-agnostic async AI completion (OpenAI/Anthropic/Gemini/OpenRouter)
  token_utils.py  # Token counting (tiktoken) + page aggregation for crawl/analyze
  main.py         # FastAPI app + route wiring
```

### Scrape flow
1. Try httpx (fast, no JS)
2. If body is thin (<200 chars), JS markers found, or `waitFor>0` → fallback to Playwright
3. Clean HTML: remove `<script>/<style>/nav/footer/ads`, extract main content
4. Convert to markdown via markdownify

### Crawl flow
BFS from the seed URL; respects `maxDepth`, `limit`, `allowBackwardLinks`. Uses httpx-only (no Playwright) for speed. Results stored in Redis, expired after 1 hour. robots.txt is fetched once per domain and cached for the duration of the crawl; disallowed URLs are skipped. Failed requests are retried up to `SCRAPE_MAX_RETRIES` times with exponential backoff (base `SCRAPE_RETRY_BACKOFF` seconds), honouring `Retry-After` headers on 429 responses.

### AI analysis flow
AI endpoints run in the API process (not the Celery worker):
1. **Scrape/analyze or scrape/summarize**: scrapes URL → passes markdown + prompt to AI provider → returns response
2. **Crawl/analyze**: reads completed crawl results from Redis → aggregates markdowns with token budget enforced (80K token ceiling via `tiktoken`) → passes to AI → returns analysis with `pages_analyzed` and `was_truncated` fields
3. Provider and model are selected via `AI_PROVIDER` / `AI_MODEL` env vars. If `AI_MODEL` is empty, a sensible default is chosen per provider.

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/scrape` | Scrape single URL → markdown/html |
| POST | `/v1/scrape/analyze` | Scrape URL → AI analysis with custom prompt |
| POST | `/v1/scrape/summarize` | Scrape URL → AI summary (default prompt) |
| POST | `/v1/crawl` | Start async crawl, returns `{id}` |
| GET | `/v1/crawl/{id}` | Poll status + results |
| DELETE | `/v1/crawl/{id}` | Cancel crawl |
| POST | `/v1/crawl/analyze` | AI analysis of a completed crawl job |

## Configuration (`.env`)

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3002` | API port |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Nav timeout (ms) |
| `MAX_CONCURRENCY` | `5` | Parallel Playwright pages |
| `API_KEY` | _(empty)_ | Bearer token auth (disabled if empty) |
| `CRAWL_RESPECT_ROBOTS` | `true` | Honour robots.txt during crawls |
| `SCRAPE_MAX_RETRIES` | `3` | Max retries on transient errors / 429 / 5xx |
| `SCRAPE_RETRY_BACKOFF` | `1.0` | Base backoff (seconds); doubles each retry |

### AI

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `openai` | Provider: `openai` \| `anthropic` \| `gemini` \| `openrouter` |
| `AI_MODEL` | _(empty)_ | Model name; empty = provider default (see below) |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key |
| `ANTHROPIC_API_KEY` | _(empty)_ | Anthropic API key |
| `GEMINI_API_KEY` | _(empty)_ | Google Gemini API key |
| `OPENROUTER_API_KEY` | _(empty)_ | OpenRouter API key |
| `AI_MAX_TOKENS_INPUT` | `100000` | Char ceiling per page before token counting (crawl/analyze) |
| `AI_MAX_PAGES` | `50` | Max pages aggregated for crawl/analyze |
| `AI_SUMMARIZE_PROMPT` | _(built-in)_ | Default system prompt for `/v1/scrape/summarize` |

### Provider defaults (when `AI_MODEL` is empty)

| Provider | Default model |
|----------|--------------|
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-3-5-haiku-20241022` |
| `gemini` | `gemini-1.5-flash` |
| `openrouter` | `openai/gpt-4o-mini` |

## Error codes

| Status | Scenario |
|--------|----------|
| 401 | Missing or invalid `API_KEY` |
| 404 | Crawl job not found |
| 409 | Crawl/analyze called on an in-progress crawl |
| 422 | No markdown extracted from page, or all crawled pages are empty |
| 400 | AI provider returned an error (bad key, rate limit, invalid model, etc.) |
| 500 | Scrape/fetch error |
