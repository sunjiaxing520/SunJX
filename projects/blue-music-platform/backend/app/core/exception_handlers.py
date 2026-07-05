from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.errors import ErrorDetail, ErrorResponse


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: object | None = None,
) -> JSONResponse:
    content = ErrorResponse(
        error=ErrorDetail(code=code, message=message, detail=detail)
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "request failed"
    return _error_response(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=message,
        detail=None if isinstance(exc.detail, str) else exc.detail,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="request validation failed",
        detail=exc.errors(),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="internal server error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
