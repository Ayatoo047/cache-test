"""Payload generation with cached transformations."""

import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy.orm import Session

from cache_test.models import Payload
from cache_test.repositories import payload_repo, transfomer_repo
from cache_test.transformer import Transformer


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


def hash_inputs(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """The lists are serialised as a whole (not concatenated strings) so that
    ["a,b"]  and ["a", "b"] will not produce the same hash.
    """
    canonical = json.dumps(
        [list(list_1), list(list_2)], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class PayloadService:
    def __init__(self, session: Session, transformer: Transformer) -> None:
        self._session = session
        self._transformer = transformer

    def create_payload(
        self, list_1: Sequence[str], list_2: Sequence[str]
    ) -> tuple[Payload, bool]:
        """Return the payload for the given lists and whether it was newly created.

        An identical earlier request short-circuits everything, including
        cache lookups, and yields the previously issued identifier.
        """
        if len(list_1) != len(list_2):
            raise ValueError("list_1 and list_2 must have the same length")

        input_hash = hash_inputs(list_1, list_2)
        existing = payload_repo.get_payload_by_hash(self._session, input_hash)
        if existing is not None:
            return existing, False

        transformed = self._transform_all([*list_1, *list_2])
        output = ", ".join(
            interleave(
                [transformed[s] for s in list_1], [transformed[s] for s in list_2]
            )
        )
        payload, created = payload_repo.add_payload(self._session, input_hash, output)
        self._session.commit()
        return payload, created

    def get_payload(self, payload_id: uuid.UUID) -> Payload | None:
        return payload_repo.get_payload(self._session, payload_id)

    def _transform_all(self, values: Iterable[str]) -> dict[str, str]:
        """Transform each distinct value, calling the transformer only on cache misses."""
        unique = list(dict.fromkeys(values))
        results = transfomer_repo.get_transformations(self._session, unique)

        fresh: dict[str, str] = {}
        try:
            for value in unique:
                if value not in results:
                    fresh[value] = self._transformer(value)
        finally:
            # Persist whatever the transformer produced even if a later call
            # failed, so a retry does not pay for those results again.
            transfomer_repo.add_transformations(self._session, fresh)
            self._session.commit()

        return results | fresh
