"""Application settings loaded from the environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, read from the names frozen in 02-ARCHITECTURE.md §10."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    BIFROST_URL: str = "http://localhost:8080"
    PRIMARY_MODEL: str = ""
    FALLBACK_MODEL: str = ""
    WEAK_MODEL: str = ""
    TAVILY_API_KEY: str = ""
    MAX_CLAIMS: int = 8
    MAX_PARALLEL: int = 4
    REQUEST_TIMEOUT_S: float = 25
    CACHE_DB: str = "ttl_cache.db"

    @property
    def tavily_key_set(self) -> bool:
        """True only when a Tavily key is present; never exposes the value."""
        return bool(self.TAVILY_API_KEY.strip())


settings = Settings()
