"""Request and response bodies of the HTTP API."""

import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator


class PayloadCreate(BaseModel):
    list_1: list[str] = Field(min_length=1)
    list_2: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_same_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: uuid.UUID


class PayloadRead(BaseModel):
    output: str
