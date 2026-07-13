import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.schemas.errors import ErrorDetail, ErrorResponse


logger = logging.getLogger(f"{LOGGER_NAME}.errors")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    detail: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            detail=detail,
        )
    ).model_dump(exclude_none=True)
    response_headers = {REQUEST_ID_HEADER: request_id, **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=response_headers,
    )


def _log_request_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    exc: Exception | None = None,
) -> None:
    context = {
        "request_id": get_request_id(request),
        "user_id": getattr(request.state, "user_id", None),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "error_code": code,
    }
    if exc is None:
        logger.warning("request_failed", extra=context)
        return

    logger.error(
        "request_failed",
        extra=context,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def _validation_error_detail(exc: RequestValidationError) -> list[dict[str, object]]:
    return [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    _log_request_error(
        request,
        status_code=exc.status_code,
        code=exc.code,
    )
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        detail=exc.detail,
        headers=exc.headers,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    default_messages = {
        status.HTTP_401_UNAUTHORIZED: "身份认证失败",
        status.HTTP_403_FORBIDDEN: "没有操作权限",
        status.HTTP_404_NOT_FOUND: "请求的接口或资源不存在",
        status.HTTP_405_METHOD_NOT_ALLOWED: "请求方法不允许",
    }
    message = default_messages.get(exc.status_code, "请求失败")
    code = f"HTTP_{exc.status_code}"
    _log_request_error(
        request,
        status_code=exc.status_code,
        code=code,
    )
    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        request_id=get_request_id(request),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    _log_request_error(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
    )
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="请求参数校验失败",
        request_id=get_request_id(request),
        detail=_validation_error_detail(exc),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    _log_request_error(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        exc=exc,
    )
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="服务器内部错误",
        request_id=get_request_id(request),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
