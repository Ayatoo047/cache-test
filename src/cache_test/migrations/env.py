"""Alembic environment.

Runs in two ways: from the app at startup, which passes in its own connection
(so in-memory test databases work), and from the ``alembic`` command line,
which connects using the service's own settings.
"""

from alembic import context
from sqlalchemy import Connection

from cache_test import models  # noqa: F401  (registers tables on Base.metadata)
from cache_test.config import Settings
from cache_test.db import Base, create_db_engine

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite can't alter most column properties in place; batch mode
        # recreates the table instead, so later migrations work on both
        # SQLite and PostgreSQL.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    engine = create_db_engine(Settings().database_url)
    with engine.connect() as connection:
        _run(connection)
    engine.dispose()
