"""Service configuration, read from environment variables prefixed with ``cache_test_``."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_TEST_")

    # SQLite keeps the service self-contained; any SQLAlchemy URL works, and
    # the conflict-tolerant inserts in the repository also support PostgreSQL.
    database_url: str = "sqlite:///./cache.db"