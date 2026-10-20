"""Persistence operations for payloads."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from cache_test.models import Payload
from cache_test.repositories._inserts import insert_ignoring_conflicts


def get_payload(session: Session, payload_id: uuid.UUID) -> Payload | None:
    return session.get(Payload, payload_id)


def get_payload_by_hash(session: Session, input_hash: str) -> Payload | None:
    return session.scalars(select(Payload).where(Payload.input_hash == input_hash)).one_or_none()


def add_payload(session: Session, input_hash: str, output: str) -> tuple[Payload, bool]:
    """Store a payload unless one already exists for ``input_hash``.

    Returns the stored payload and whether this call created it.
    """
    result = session.execute(
        insert_ignoring_conflicts(session, Payload).values(
            id=uuid.uuid4(), input_hash=input_hash, output=output
        )
    )
    payload = get_payload_by_hash(session, input_hash)
    assert payload is not None  # Either just inserted or inserted concurrently.
    return payload, result.rowcount == 1
