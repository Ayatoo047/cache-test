import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from cache_test import models
from cache_test.db import BASELINE_REVISION, Base, create_db_engine, init_db


def test_migrations_create_all_tables() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)

    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "payloads",
        "transformations",
    }


def test_migrations_match_models() -> None:
    # Fails when a model changes without a matching migration.
    engine = create_db_engine("sqlite://")
    init_db(engine)

    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_init_db_is_idempotent() -> None:
    # The app runs migrations on every startup, including against an
    # up-to-date database.
    engine = create_db_engine("sqlite://")
    init_db(engine)
    init_db(engine)

    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() is not None


@pytest.mark.parametrize("empty_version_table", [False, True], ids=["no-table", "empty-table"])
def test_adopts_database_created_before_migrations(empty_version_table: bool) -> None:
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    if empty_version_table:
        # Left behind by an earlier upgrade attempt that failed on these tables.
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
    with engine.begin() as connection:
        connection.execute(models.Transformation.__table__.insert().values(input="a", output="A"))

    init_db(engine)

    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE_REVISION
        assert connection.execute(models.Transformation.__table__.select()).all()
