from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    playwright_timeout: int = 30000
    max_concurrency: int = 5
    api_key: str = ""
    port: int = 3002

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
