"""Application settings, read from environment variables (and a local .env file).

Configuration is not code: the same code runs on your laptop and on Render with
different values. Never hard-code keys or URLs here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0  # give up on a slow AI call
    llm_max_output_tokens: int = 800  # cap on the length of any one AI answer
    database_url: str = "sqlite:///./knowledge.db"
    allowed_origins: str = "http://localhost:5173"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Create the settings once and reuse them."""
    return Settings()
