"""Inserts that tolerate unique-constraint conflicts.

Inserts use ``ON CONFLICT DO NOTHING`` so that concurrent requests producing
the same rows do not fail on unique constraints: whichever request wins, the
stored value is identical, so the loser can simply read it back.
"""

from sqlalchemy import Insert
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

_DIALECT_INSERTS = {"sqlite": sqlite.insert, "postgresql": postgresql.insert}


def insert_ignoring_conflicts(session: Session, model: type) -> Insert:
    dialect = session.get_bind().dialect.name
    try:
        insert = _DIALECT_INSERTS[dialect]
    except KeyError:
        raise NotImplementedError(f"Unsupported database dialect: {dialect}") from None
    return insert(model).on_conflict_do_nothing()
