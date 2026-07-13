import logging

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.config import settings
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth import authenticate_user
from app.services.users import user_response


router = APIRouter(prefix="/auth")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    payload: LoginRequest,
    db: DatabaseSession,
) -> TokenResponse:
    user = authenticate_user(
        db,
        username=payload.username,
        password=payload.password.get_secret_value(),
    )
    audit_logger.info(
        "auth_login_succeeded",
        extra={"request_id": get_request_id(request), "user_id": user.id},
    )
    return TokenResponse(
        access_token=create_access_token(user.id, user.token_version),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def current_user_profile(current_user: CurrentUser) -> UserResponse:
    return user_response(current_user)
