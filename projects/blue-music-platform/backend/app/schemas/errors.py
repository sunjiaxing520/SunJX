from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    detail: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
