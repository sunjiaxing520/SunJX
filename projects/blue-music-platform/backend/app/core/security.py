from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import status
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import AppException


password_hasher = PasswordHash.recommended()
BEARER_HEADERS = {"WWW-Authenticate": "Bearer"}


def validate_security_settings() -> None:
    if settings.ENVIRONMENT != "production":
        return

    if (
        settings.SECRET_KEY == "dev_secret_key_change_in_production"
        or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError(
            "Production SECRET_KEY must be a non-default value with "
            "at least 32 characters"
        )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: int, token_version: int) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
        "jti": uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, object]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppException(
            code="AUTH_TOKEN_EXPIRED",
            message="登录凭证已过期，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AppException(
            code="AUTH_TOKEN_INVALID",
            message="登录凭证无效，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        ) from exc

    if (
        payload.get("type") != "access"
        or not payload.get("sub")
        or not isinstance(payload.get("ver"), int)
    ):
        raise AppException(
            code="AUTH_TOKEN_INVALID",
            message="登录凭证无效，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        )
    return payload
