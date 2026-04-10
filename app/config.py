from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    playwright_timeout: int = 30000
    max_concurrency: int = 5
    api_key: str = ""
    port: int = 3002

    # AI provider
    ai_provider: Literal["openai", "anthropic", "gemini", "openrouter"] = "openai"
    ai_model: str = ""

    # Per-provider API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Crawl politeness
    crawl_respect_robots: bool = True      # CRAWL_RESPECT_ROBOTS env var

    # Retry / backoff
    scrape_max_retries: int = 3            # SCRAPE_MAX_RETRIES
    scrape_retry_backoff: float = 1.0      # SCRAPE_RETRY_BACKOFF (seconds, base)

    # Token budget controls
    ai_max_tokens_input: int = 100_000  # char ceiling per page before token counting
    ai_max_pages: int = 50              # max pages aggregated for crawl/analyze
    ai_summarize_prompt: str = (
        "Summarize the following web page content concisely. "
        "Include the main topic, key points, and any important details."
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
