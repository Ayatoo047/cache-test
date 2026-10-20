"""Database engine and session construction."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    if not database_url.startswith("sqlite"):
        return create_engine(database_url, pool_pre_ping=True)

    # FastAPI runs sync endpoints in a thread pool, so connections must be
    # allowed to cross threads. An in-memory database only exists for the
    # lifetime of a single connection, hence the shared StaticPool.
    in_memory = database_url in ("sqlite://", "sqlite:///:memory:")
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if in_memory else None,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# The first migration, matching the schema create_all used to build.
BASELINE_REVISION = "a10eeb321d04"


def init_db(engine: Engine) -> None:
    """Bring the schema up to date by running any pending Alembic migrations.

    Running them on startup keeps a single-instance deployment to one command.
    With several instances, migrations would move to a separate deploy step,
    so instances don't race to apply them.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        # Reusing the app's connection lets in-memory databases (one per
        # connection) be migrated, and keeps env.py from opening its own.
        config.attributes["connection"] = connection
        unversioned = MigrationContext.configure(connection).get_current_revision() is None
        if unversioned and inspect(connection).has_table("payloads"):
            # Created by create_all before migrations existed; its schema
            # equals the first revision, so record that instead of re-creating.
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")
