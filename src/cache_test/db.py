"""Database engine and session construction."""

from sqlalchemy import Engine, create_engine
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


def init_db(engine: Engine) -> None:
    # Schema migrations (e.g. Alembic) are out of scope for this service;
    # creating missing tables on startup is sufficient for a single schema version.
    from cache_test import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(engine)
