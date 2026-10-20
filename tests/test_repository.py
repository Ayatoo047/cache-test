from sqlalchemy.orm import Session

from cache_test.repositories import payload_repo, transformer_repo


def test_add_payload_returns_existing_row_on_conflict(session: Session) -> None:
    # Simulates two concurrent requests racing to store the same payload.
    first, first_created = payload_repo.add_payload(session, "hash", "OUTPUT")
    second, second_created = payload_repo.add_payload(session, "hash", "OUTPUT")

    assert (first_created, second_created) == (True, False)
    assert second.id == first.id


def test_add_transformations_ignores_existing_entries(session: Session) -> None:
    transformer_repo.add_transformations(session, {"a": "A"})
    transformer_repo.add_transformations(session, {"a": "A", "b": "B"})

    assert transformer_repo.get_transformations(session, ["a", "b", "missing"]) == {
        "a": "A",
        "b": "B",
    }


def test_get_transformations_with_no_inputs(session: Session) -> None:
    assert transformer_repo.get_transformations(session, []) == {}
