"""Persistence operations for transformations"""

from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from cache_test.models import Transformation
from cache_test.repositories._inserts import insert_ignoring_conflicts


def get_transformations(session: Session, inputs: Iterable[str]) -> dict[str, str]:
    inputs = list(inputs)
    if not inputs:
        return {}
    rows = session.execute(
        select(Transformation.input, Transformation.output).where(
            Transformation.input.in_(inputs)
        )
    )
    return {row.input: row.output for row in rows}


def add_transformations(session: Session, outputs: Mapping[str, str]) -> None:
    if not outputs:
        return
    session.execute(
        insert_ignoring_conflicts(session, Transformation),
        [{"input": key, "output": value} for key, value in outputs.items()],
    )
