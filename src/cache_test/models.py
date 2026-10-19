"""ORM models for cached transformations and generated payloads."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from cache_test.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Transformation(Base):
    """Result of a single transformer call, keyed by its input string."""

    __tablename__ = "transformations"

    input: Mapped[str] = mapped_column(Text, primary_key=True)
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Payload(Base):
    """A generated payload.

    ``input_hash`` identifies the request that produced the payload, so that
    repeating a request returns the existing identifier instead of a new one.
    """

    __tablename__ = "payloads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
