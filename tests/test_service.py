import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cache_test.models import Transformation
from cache_test.services.payload import PayloadService, hash_inputs, interleave
from tests.conftest import CountingTransformer

LIST_1 = ["first string", "second string", "third string"]
LIST_2 = ["other string", "another string", "last string"]


class TestInterleave:
    def test_alternates_items(self) -> None:
        assert interleave(["a", "b"], ["1", "2"]) == ["a", "1", "b", "2"]

    def test_empty(self) -> None:
        assert interleave([], []) == []

    def test_rejects_different_lengths(self) -> None:
        with pytest.raises(ValueError):
            interleave(["a"], [])


class TestHashInputs:
    def test_is_deterministic(self) -> None:
        assert hash_inputs(LIST_1, LIST_2) == hash_inputs(list(LIST_1), list(LIST_2))

    def test_depends_on_list_order(self) -> None:
        assert hash_inputs(LIST_1, LIST_2) != hash_inputs(LIST_2, LIST_1)

    def test_does_not_confuse_item_boundaries(self) -> None:
        assert hash_inputs(["a,b"], ["c"]) != hash_inputs(["a", "b"], ["c"])


class TestPayloadService:
    def test_generates_interleaved_output(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        payload, created = PayloadService(session, transformer).create_payload(
            LIST_1, LIST_2
        )

        assert created
        assert payload.output == (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        )

    def test_repeated_request_reuses_identifier_without_transforming(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        service = PayloadService(session, transformer)
        first, _ = service.create_payload(LIST_1, LIST_2)
        calls_after_first = transformer.total_calls

        second, created = service.create_payload(LIST_1, LIST_2)

        assert not created
        assert second.id == first.id
        assert transformer.total_calls == calls_after_first

    def test_transforms_each_distinct_string_once(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        PayloadService(session, transformer).create_payload(
            ["a", "b", "a"], ["b", "c", "a"]
        )

        assert transformer.calls == {"a": 1, "b": 1, "c": 1}

    def test_reuses_cached_transformations_across_payloads(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        service = PayloadService(session, transformer)
        service.create_payload(["a", "b"], ["c", "d"])

        payload, created = service.create_payload(["d", "c"], ["b", "e"])

        assert created
        assert payload.output == "D, B, C, E"
        assert transformer.calls == {"a": 1, "b": 1, "c": 1, "d": 1, "e": 1}

    def test_persists_transformations_completed_before_a_failure(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        def flaky(value: str) -> str:
            if value == "boom":
                raise RuntimeError("service unavailable")
            return transformer(value)

        with pytest.raises(RuntimeError):
            PayloadService(session, flaky).create_payload(["a", "boom"], ["b", "c"])

        cached = session.scalar(select(func.count()).select_from(Transformation))
        assert cached == 1  # Only "a" was transformed before the failure.

    def test_rejects_lists_of_different_length(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        with pytest.raises(ValueError):
            PayloadService(session, transformer).create_payload(["a"], ["b", "c"])
        assert transformer.total_calls == 0

    def test_get_payload_returns_none_for_unknown_id(
        self, session: Session, transformer: CountingTransformer
    ) -> None:
        assert PayloadService(session, transformer).get_payload(uuid.uuid4()) is None