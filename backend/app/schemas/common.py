from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    data: T


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    total: int


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: object | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class MessageResponse(BaseModel):
    message: str = Field(default="ok")


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
