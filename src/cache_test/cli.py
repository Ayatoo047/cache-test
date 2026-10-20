"""``cache-cli``: exercise the caching service from the command line.

Each iteration creates a payload and reads it back, writing one JSON line per
iteration. Repeating a request shows the caching at work: the identifier
stays the same and later iterations are much faster than the first.
"""

import argparse
import contextlib
import json
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Literal, Self, TextIO

import httpx
from pydantic import (
    Field,
    FilePath,
    HttpUrl,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, CliSettingsSource, SettingsConfigDict

from cache_test.schemas.payload import PayloadCreate



class CliSettings(BaseSettings):
    """Create payloads on the caching service and read them back."""

    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        cli_shortcuts={"host": "h", "repeat": "r", "input": "i", "json": "j", "output": "o"},
        cli_hide_none_type=True,
        # Without a prefix, common shell variables such as HOST would silently
        # override the defaults.
        env_prefix="CACHE_CLI_",
    )

    host: HttpUrl = Field(HttpUrl("http://localhost:8000"), description="URL of the service")
    repeat: PositiveInt = Field(1, description="number of iterations")
    input: Literal["-"] | FilePath | None = Field(
        None, description='JSON input file, "-" for stdin (default when --json is not given)'
    )
    json_: str | None = Field(None, alias="json", description="JSON input given inline")
    output: Literal["-"] | Path = Field("-", description='output file, "-" for stdout')

    @field_validator("json_")
    @classmethod
    def _check_json(cls, value: str | None) -> str | None:
        # Reject malformed input before any request is made.
        if value is not None:
            PayloadCreate.model_validate_json(value)
        return value

    @model_validator(mode="after")
    def _check_single_input(self) -> Self:
        if self.input is not None and self.json_ is not None:
            raise ValueError("--input and --json are mutually exclusive")
        return self

    def load_request(self, stdin: TextIO) -> PayloadCreate:
        if self.json_ is not None:
            raw = self.json_
        elif self.input is None or self.input == "-":
            raw = stdin.read()
        else:
            raw = self.input.read_text()
        return PayloadCreate.model_validate_json(raw)


def parse_args(argv: Sequence[str] | None = None) -> CliSettings:
    # The spec assigns -h to --host, so argparse's built-in -h/--help is
    # replaced by a --help-only flag.
    parser = argparse.ArgumentParser(prog="cache-cli", add_help=False)
    parser.add_argument("--help", action="help", help="show this help message and exit")
    source = CliSettingsSource(CliSettings, root_parser=parser)
    args = True if argv is None else list(argv)  # True means "parse sys.argv".
    return CliSettings(_cli_settings_source=source(args=args))


def run(client: httpx.Client, request: PayloadCreate, repeat: int, out: TextIO) -> None:
    for iteration in range(1, repeat + 1):
        started = time.perf_counter()
        created = client.post("/payload", json=request.model_dump())
        created.raise_for_status()
        payload_id = created.json()["data"]["id"]
        read = client.get(f"/payload/{payload_id}")
        read.raise_for_status()
        elapsed_ms = (time.perf_counter() - started) * 1000

        record = {
            "iteration": iteration,
            "id": payload_id,
            "created": created.status_code == httpx.codes.CREATED,
            "output": read.json()["data"]["output"],
            "elapsed_ms": round(elapsed_ms, 1),
        }
        out.write(json.dumps(record) + "\n")
        out.flush()


@contextlib.contextmanager
def _open_output(output: Path | str) -> Iterator[TextIO]:
    if output == "-":
        yield sys.stdout
    else:
        with Path(output).open("w") as file:
            yield file


def _describe_validation_error(exc: ValidationError) -> str:
   return f"invalid input: {str(exc)}"


def _describe_http_error(exc: httpx.HTTPError) -> str:
    return f"request failed: {exc}" if not isinstance(exc, httpx.HTTPStatusError) else "Request failed with HTTP status error"


def main(argv: Sequence[str] | None = None) -> int:
    try:
        settings = parse_args(argv)
        request = settings.load_request(sys.stdin)
    except ValidationError as exc:
        print(f"cache-cli: invalid input\n{_describe_validation_error(exc)}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cache-cli: cannot read input: {exc}", file=sys.stderr)
        return 2

    try:
        with (
            httpx.Client(base_url=str(settings.host), timeout=30) as client,
            _open_output(settings.output) as out,
        ):
            run(client, request, settings.repeat, out)
    except httpx.HTTPError as exc:
        print(f"cache-cli: {_describe_http_error(exc)}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"cache-cli: cannot write output: {exc}", file=sys.stderr)
        return 1
    return 0