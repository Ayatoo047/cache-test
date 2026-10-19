"""Uniform response envelope shared by every endpoint, successful or not.

Every response body has the same shape::

    {"requestId": "...", "message": "...", "status": 200, "data": {...}, "errors": null}

so clients can parse any response the same way. ``data`` is null on errors;
``errors`` is only populated for validation failures (422).
"""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# Caller-supplied ids are echoed back in headers and logs, so only accept
# short, plain tokens; anything else is replaced with a fresh id.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


class FieldError(BaseModel):
    field: str
    message: str


class ApiResponse[T](BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    request_id: str
    message: str
    status: int
    data: T | None = None
    errors: list[FieldError] | None = None


class ErrorResponse(ApiResponse[None]):
    """Body of every error response; a named subclass gives it a readable schema name."""


def get_request_id(request: Request) -> str:
    return request.state.request_id


def _error_response(
    request: Request,
    status_code: int,
    message: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        request_id=get_request_id(request),
        message=message,
        status=status_code,
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body, by_alias=True),
        headers={**(headers or {}), REQUEST_ID_HEADER: get_request_id(request)},
    )


def _success[T](
    request: Request,
    response: Response,
    data: T,
    message: str,
    status_code: int = status.HTTP_200_OK,
) -> ApiResponse[T]:
    # The envelope repeats the status so clients reading only the body (e.g.
    # from logs or queues) still know the outcome.
    response.status_code = status_code
    return ApiResponse(
        request_id=get_request_id(request),
        message=message,
        status=status_code,
        data=data,
    )


async def _assign_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request.state.request_id = (
        incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
    )
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request.state.request_id
    return response


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(
        request, exc.status_code, str(exc.detail), headers=exc.headers
    )


async def _validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic's raw errors echo the offending input back, which can be as
    # large as the request itself; only the location and reason are kept.
    errors = [
        FieldError(
            field=".".join(str(part) for part in error["loc"]),
            # Pydantic prefixes messages from custom validators; drop the noise.
            message=error["msg"].removeprefix("Value error, "),
        )
        for error in exc.errors()
    ]
    return _error_response(
        request, status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", errors=errors
    )


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # Starlette re-raises the exception after this handler, so the server logs
    # the traceback; this line links it to the request id the client saw.
    logger.error("Unhandled error for request %s", get_request_id(request))
    return _error_response(
        request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error"
    )


def install(app: FastAPI) -> None:
    app.middleware("http")(_assign_request_id)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
