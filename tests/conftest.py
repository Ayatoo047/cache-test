from collections import Counter
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from cache_test.db import create_db_engine, create_session_factory, init_db


class CountingTransformer:
    """Upper-casing transformer that records every call it receives."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()

    def __call__(self, value: str) -> str:
        self.calls[value] += 1
        return value.upper()

    @property
    def total_calls(self) -> int:
        return self.calls.total()


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_db_engine("sqlite://")
    init_db(engine)
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()
