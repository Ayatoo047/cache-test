"""Integration tests: HTTP requests through FastAPI down to a real SQLite file."""

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cache_test.config import Settings
from cache_test.main import create_app
from cache_test.transformer import TransformerError
from tests.conftest import CountingTransformer

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
ENVELOPE_KEYS = {"requestId", "message", "status", "data", "errors"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(
    settings: Settings, transformer: CountingTransformer
) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transformer)) as client:
        yield client


def assert_envelope(response: Any, status: int, message: str) -> dict[str, Any]:
    body = response.json()
    assert response.status_code == status
    assert set(body) == ENVELOPE_KEYS
    assert body["status"] == status
    assert body["message"] == message
    assert body["requestId"] == response.headers["X-Request-ID"]
    return body


def create(client: TestClient, body: dict = SAMPLE) -> str:
    return client.post("/payload", json=body).json()["data"]["id"]


def test_create_then_read_payload(client: TestClient) -> None:
    created = assert_envelope(
        client.post("/payload", json=SAMPLE), 201, "Payload created"
    )
    assert created["errors"] is None

    read = assert_envelope(
        client.get(f"/payload/{created['data']['id']}"), 200, "Payload retrieved"
    )

    assert read["data"] == {
        "output": (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        )
    }


def test_repeated_request_returns_same_id(
    client: TestClient, transformer: CountingTransformer
) -> None:
    first_id = create(client)

    second = assert_envelope(
        client.post("/payload", json=SAMPLE), 200, "Payload already exists"
    )

    assert second["data"] == {"id": first_id}
    assert transformer.total_calls == 6


def test_cache_survives_restart(
    settings: Settings, transformer: CountingTransformer
) -> None:
    with TestClient(create_app(settings, transformer)) as client:
        payload_id = create(client, {"list_1": ["a"], "list_2": ["b"]})

    with TestClient(create_app(settings, transformer)) as client:
        assert client.get(f"/payload/{payload_id}").json()["data"] == {"output": "A, B"}
        create(client, {"list_1": ["b"], "list_2": ["a"]})

    assert transformer.calls == {"a": 1, "b": 1}

def test_read_payload_is_cacheable_for_an_hour(client: TestClient) -> None:
    response = client.get(f"/payload/{create(client)}")

    assert response.headers["Cache-Control"] == "public, max-age=3600"

def test_read_unknown_payload_returns_404(client: TestClient) -> None:
    response = client.get(f"/payload/{uuid.uuid4()}")

    body = assert_envelope(response, 404, "Payload not found")
    assert body["data"] is None
    assert "Cache-Control" not in response.headers


def test_read_malformed_id_returns_422(client: TestClient) -> None:
    body = assert_envelope(client.get("/payload/not-a-uuid"), 422, "Invalid request")

    assert [error["field"] for error in body["errors"]] == ["path.payload_id"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"list_1": ["a"], "list_2": ["b", "c"]}, "body"),
        ({"list_1": [], "list_2": []}, "body.list_1"),
        ({"list_1": ["a"]}, "body.list_2"),
        ({"list_1": ["a"], "list_2": [1]}, "body.list_2.0"),
    ],
    ids=["different-lengths", "empty", "missing-list", "non-string"],
)
def test_invalid_input_returns_422(
    client: TestClient, transformer: CountingTransformer, body: dict, field: str
) -> None:
    response = assert_envelope(
        client.post("/payload", json=body), 422, "Invalid request"
    )

    assert response["data"] is None
    assert field in [error["field"] for error in response["errors"]]
    assert transformer.total_calls == 0


def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    body = client.post("/payload", json={"list_1": ["a"], "list_2": ["b", "c"]}).json()

    assert body["errors"] == [
        {"field": "body", "message": "list_1 and list_2 must have the same length"}
    ]


def test_transformer_failure_returns_502(settings: Settings) -> None:
    def failing(value: str) -> str:
        raise TransformerError("upstream timeout")

    with TestClient(create_app(settings, failing)) as client:
        response = client.post("/payload", json=SAMPLE)

    assert_envelope(response, 502, "Transformer failed: upstream timeout")


def test_unexpected_error_returns_json_500(settings: Settings) -> None:
    def buggy(value: str) -> str:
        raise RuntimeError("bug")

    with TestClient(
        create_app(settings, buggy), raise_server_exceptions=False
    ) as client:
        response = client.post("/payload", json=SAMPLE)

    body = assert_envelope(response, 500, "Internal server error")
    assert "bug" not in response.text  # Internal details stay in the server logs.
    assert body["data"] is None


@pytest.mark.parametrize(
    ("method", "path", "status", "message"),
    [
        ("get", "/nowhere", 404, "Not Found"),
        ("delete", "/payload", 405, "Method Not Allowed"),
    ],
)
def test_routing_errors_use_envelope(
    client: TestClient, method: str, path: str, status: int, message: str
) -> None:
    assert_envelope(client.request(method, path), status, message)


def test_health_uses_envelope(client: TestClient) -> None:
    body = assert_envelope(client.get("/health"), 200, "Service is healthy")

    assert body["data"] == {"status": "ok"}


class TestRequestId:
    def test_generated_when_absent(self, client: TestClient) -> None:
        first = client.get("/health").json()["requestId"]
        second = client.get("/health").json()["requestId"]

        assert first != second

    def test_propagates_caller_id(self, client: TestClient) -> None:
        response = client.get("/health", headers={"X-Request-ID": "trace-123"})

        assert response.json()["requestId"] == "trace-123"
        assert response.headers["X-Request-ID"] == "trace-123"

    @pytest.mark.parametrize("unsafe", ["has spaces", "x" * 129, "line\tbreak"])
    def test_replaces_unsafe_caller_id(self, client: TestClient, unsafe: str) -> None:
        response = client.get("/health", headers={"X-Request-ID": unsafe})

        assert response.json()["requestId"] != unsafe
