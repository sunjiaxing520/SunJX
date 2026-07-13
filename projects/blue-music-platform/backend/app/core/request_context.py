import re
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


REQUEST_ID_HEADER = "X-Request-ID"
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "request-id-unavailable")


def _request_id_from_header(request: Request) -> str | None:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if request_id and VALID_REQUEST_ID.fullmatch(request_id):
        return request_id
    return None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = _request_id_from_header(request) or uuid4().hex
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response
