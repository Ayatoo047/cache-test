import io
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cache_test import cli
from cache_test.config import Settings
from cache_test.main import create_app
from cache_test.transformer import TransformerError
from tests.conftest import CountingTransformer

REQUEST = {"list_1": ["a", "b"], "list_2": ["c", "d"]}
REQUEST_JSON = json.dumps(REQUEST)


class TestParseArgs:
    def test_defaults(self) -> None:
        settings = cli.parse_args([])

        assert str(settings.host) == "http://localhost:8765/"
        assert settings.repeat == 1
        assert settings.input is None
        assert settings.output == "-"

    def test_short_flags(self, tmp_path: Path) -> None:
        output = tmp_path / "out.jsonl"
        settings = cli.parse_args(
            ["-h", "http://example.com:9000", "-r", "3", "-j", REQUEST_JSON, "-o", str(output)]
        )

        assert str(settings.host) == "http://example.com:9000/"
        assert settings.repeat == 3
        assert settings.json_ == REQUEST_JSON
        assert settings.output == output

    def test_ignores_unprefixed_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "not-a-url")

        assert str(cli.parse_args([]).host) == "http://localhost:8765/"

    @pytest.mark.parametrize(
        "argv",
        [
            ["--repeat", "0"],
            ["--host", "not a url"],
            ["--json", "{not json"],
            ["--json", '{"list_1": ["a"], "list_2": []}'],
            ["--input", "does-not-exist.json"],
            ["--input", "-", "--json", REQUEST_JSON],
        ],
        ids=[
            "zero-repeat",
            "bad-host",
            "malformed-json",
            "invalid-request",
            "missing-file",
            "both",
        ],
    )
    def test_rejects_invalid_arguments(self, argv: list[str]) -> None:
        with pytest.raises(ValidationError):
            cli.parse_args(argv)


class TestLoadRequest:
    def test_from_inline_json(self) -> None:
        settings = cli.parse_args(["--json", REQUEST_JSON])

        assert settings.load_request(io.StringIO()).model_dump() == REQUEST

    @pytest.mark.parametrize("argv", [[], ["--input", "-"]], ids=["implicit", "explicit"])
    def test_from_stdin(self, argv: list[str]) -> None:
        settings = cli.parse_args(argv)

        assert settings.load_request(io.StringIO(REQUEST_JSON)).model_dump() == REQUEST

    def test_from_file(self, tmp_path: Path) -> None:
        path = tmp_path / "request.json"
        path.write_text(REQUEST_JSON)

        settings = cli.parse_args(["--input", str(path)])

        assert settings.load_request(io.StringIO()).model_dump() == REQUEST


@pytest.fixture
def client(tmp_path: Path, transformer: CountingTransformer):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cli.db'}")
    with TestClient(create_app(settings, transformer)) as client:
        yield client


def test_run_repeats_request_against_service(
    client: TestClient, transformer: CountingTransformer
) -> None:
    out = io.StringIO()

    cli.run(client, cli.parse_args(["-j", REQUEST_JSON]).load_request(io.StringIO()), 3, out)

    records = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r["created"] for r in records] == [True, False, False]
    assert len({r["id"] for r in records}) == 1
    assert all(r["output"] == "A, C, B, D" for r in records)
    assert transformer.total_calls == 4


def test_main_writes_output_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: client)
    output = tmp_path / "out.jsonl"

    exit_code = cli.main(["-j", REQUEST_JSON, "-r", "2", "-o", str(output)])

    assert exit_code == 0
    assert len(output.read_text().splitlines()) == 2


def test_main_reports_invalid_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--repeat", "-1"]) == 2
    assert "repeat" in capsys.readouterr().err


def test_main_reports_server_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(client.app.state, "transformer", _failing_transformer)

    assert cli.main(["-j", REQUEST_JSON]) == 1
    error = capsys.readouterr().err
    assert "server responded 502: Transformer failed: down (request id " in error


def _failing_transformer(value: str) -> str:
    raise TransformerError("down")


def test_main_summarises_non_json_error_bodies(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, html="<html>Page not found</html>")

    real_client = httpx.Client
    monkeypatch.setattr(
        cli.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )

    assert cli.main(["-j", REQUEST_JSON]) == 1
    assert capsys.readouterr().err.strip() == "cache-cli: server responded 404: Not Found"
