"""Service configuration, read from environment variables prefixed with ``cache_test_``."""

from pydantic import NonNegativeFloat, SecretStr, field_validator
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

    # Clients must send this in the X-API-Key header to use the payload
    # endpoints. Whenever it is set, it is enforced.
    api_key: SecretStr | None = None

    # Disabled by default for local runs and the quick start. Set this to true
    # to require api_key; otherwise the service accepts any request and logs a
    # warning. Checked in create_app rather than here, so tools that only need
    # the database URL (e.g. the alembic command) don't need a key.
    api_key_required: bool = False

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        # Compose passes CACHE_TEST_API_KEY through as "" when it isn't set.
        return None if value == "" else value
