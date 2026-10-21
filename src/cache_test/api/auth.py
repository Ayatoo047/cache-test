"""API key authentication for the payload endpoints."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = "X-API-Key"

# auto_error=False so a missing key gets the same 401 and envelope as a wrong
# one, instead of FastAPI's built-in error. Declaring the header this way also
# adds an "Authorize" button to the interactive docs.
_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def require_api_key(
    request: Request, provided: Annotated[str | None, Depends(_api_key_header)]
) -> None:
    expected: str | None = request.app.state.api_key
    if expected is None:
        # No key and CACHE_TEST_API_KEY_REQUIRED=false; main.py warned at startup.
        return
    # compare_digest takes the same time however much of the key matches, so
    # response timing can't be used to guess the key one character at a time.
    if provided is None or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
