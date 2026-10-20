"""Service configuration, read from environment variables prefixed with ``cache_test_``."""

from pydantic import NonNegativeFloat
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_TEST_")

    # SQLite keeps the service self-contained. The code avoids SQLite-only SQL
    # (the conflict-tolerant inserts also cover PostgreSQL), but only SQLite is
    # tested, and PostgreSQL would also need a driver such as psycopg.
    database_url: str = "sqlite:///./cache.db"

    # Latency of the simulated external transformer, so the benefit of caching
    # is visible when exercising the service. Negative values are rejected at
    # startup rather than failing every request in time.sleep.
    transformer_delay_seconds: NonNegativeFloat = 0.1
