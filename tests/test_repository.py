import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cache_test.repositories import payload_repo, transfomer_repo


def test_add_payload_returns_existing_row(session: Session) -> None:
    first, first_created = payload_repo.add_payload(session, "hash", "OUTPUT")
    second, second_created = payload_repo.add_payload(session, "hash", "OUTPUT")

    assert (first_created, second_created) == (True, False)
    assert second.id == first.id


def test_add_and_get_transformations(session: Session) -> None:
    transfomer_repo.add_transformations(session, {"a": "A"})
    transfomer_repo.add_transformations(session, {"b": "B"})

    assert transfomer_repo.get_transformations(session, ["a", "b", "missing"]) == {"a": "A", "b": "B"}


def test_add_transformations_rejects_existing_entries(session: Session) -> None:
    transfomer_repo.add_transformations(session, {"a": "A"})

    with pytest.raises(IntegrityError):
        transfomer_repo.add_transformations(session, {"a": "A"})


def test_get_transformations_with_no_inputs(session: Session) -> None:
    assert transfomer_repo.get_transformations(session, []) == {}