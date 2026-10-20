import pytest
from pydantic import ValidationError

from cache_test.config import Settings


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_TEST_TRANSFORMER_DELAY_SECONDS", "0.5")

    assert Settings().transformer_delay_seconds == 0.5


def test_rejects_negative_transformer_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_TEST_TRANSFORMER_DELAY_SECONDS", "-1")

    with pytest.raises(ValidationError, match="transformer_delay_seconds"):
        Settings()
