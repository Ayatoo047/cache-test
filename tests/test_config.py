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


@pytest.mark.parametrize(("value", "expected"), [("", None), ("abc", "abc")])
def test_api_key_from_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: str | None
) -> None:
    # An empty value, as Compose passes for an unset variable, disables auth.
    monkeypatch.setenv("CACHE_TEST_API_KEY", value)

    api_key = Settings().api_key
    assert (api_key.get_secret_value() if api_key else None) == expected


def test_api_key_required_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CACHE_TEST_API_KEY_REQUIRED", raising=False)

    assert Settings().api_key_required is True


def test_api_key_requirement_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_TEST_API_KEY_REQUIRED", "false")

    assert Settings().api_key_required is False
