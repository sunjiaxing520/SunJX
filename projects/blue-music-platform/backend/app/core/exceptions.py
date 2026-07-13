from dataclasses import dataclass

from fastapi import status


@dataclass
class AppException(Exception):
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: object | None = None
    headers: dict[str, str] | None = None
