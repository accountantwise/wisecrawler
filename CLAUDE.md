# Firecrawl Clone

## Project Overview
A clone of Firecrawl — a web scraping and crawling API that converts websites into clean, LLM-ready markdown.

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

# Start a crawl job
curl -X POST http://localhost:3002/v1/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","limit":5}'

# Poll crawl status (replace <id> with the returned job ID)
curl http://localhost:3002/v1/crawl/<id>
```

## Architecture

Three Docker services:
- **redis** — job queue + result store (redis:7-alpine)
- **api** — FastAPI + uvicorn, handles `/v1/scrape` synchronously and `/v1/crawl` async
- **worker** — Celery worker, executes crawl jobs from the queue

```
app/
  config.py    # Settings via pydantic-settings / env vars
  models.py    # Pydantic v2 request/response schemas
  scraper.py   # fetch URL → clean markdown (httpx first, Playwright fallback)
  crawler.py   # Celery task: BFS crawl + link discovery
  markdown.py  # HTML cleaning (BS4) + html→markdown (markdownify)
  main.py      # FastAPI app + route wiring
```

### Scrape flow
1. Try httpx (fast, no JS)
2. If body is thin (<200 chars), JS markers found, or `waitFor>0` → fallback to Playwright
3. Clean HTML: remove `<script>/<style>/nav/footer/ads`, extract main content
4. Convert to markdown via markdownify

### Crawl flow
BFS from the seed URL; respects `maxDepth`, `limit`, `allowBackwardLinks`. Uses httpx-only (no Playwright) for speed. Results stored in Redis, expired after 1 hour.

## API Surface

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/v1/scrape` | Scrape single URL → markdown/html |
| POST | `/v1/crawl` | Start async crawl, returns `{id}` |
| GET | `/v1/crawl/{id}` | Poll status + results |
| DELETE | `/v1/crawl/{id}` | Cancel crawl |

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3002` | API port |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `PLAYWRIGHT_TIMEOUT` | `30000` | Nav timeout (ms) |
| `MAX_CONCURRENCY` | `5` | Parallel Playwright pages |
| `API_KEY` | _(empty)_ | Bearer token auth (disabled if empty) |
