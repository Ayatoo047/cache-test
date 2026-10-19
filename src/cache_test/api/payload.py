"""HTTP endpoints for creating and reading payloads."""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from cache_test.schemas.payload import PayloadCreate, PayloadCreated, PayloadRead
from cache_test.services.payload import PayloadService
from cache_test.utils.envelope import ApiResponse, ErrorResponse, _success

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_service(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> PayloadService:
    return PayloadService(session, request.app.state.transformer)


ServiceDep = Annotated[PayloadService, Depends(get_service)]


@router.post(
    "/payload",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": ApiResponse[PayloadCreated],
            "description": "Payload reused",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
    },
)
def create_payload(
    body: PayloadCreate, request: Request, response: Response, service: ServiceDep
) -> ApiResponse[PayloadCreated]:
    payload, created = service.create_payload(body.list_1, body.list_2)
    data = PayloadCreated(id=payload.id)
    if not created:
        # Nothing new was created, so 201 would be misleading to clients.
        return _success(request, response, data, "Payload already exists")
    return _success(request, response, data, "Payload created", status.HTTP_201_CREATED)


@router.get(
    "/payload/{payload_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def read_payload(
    payload_id: uuid.UUID, request: Request, response: Response, service: ServiceDep
) -> ApiResponse[PayloadRead]:
    payload = service.get_payload(payload_id)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payload not found")
    return _success(
        request, response, PayloadRead(output=payload.output), "Payload retrieved"
    )
