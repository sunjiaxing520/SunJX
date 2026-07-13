from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models import User


DUMMY_PASSWORD_HASH = hash_password("blue-music-dummy-password")


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.scalar(
        select(User).where(User.username == username.lower())
    )
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)

    if user is None or not password_matches:
        raise AppException(
            code="AUTH_INVALID_CREDENTIALS",
            message="账号或密码错误",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise AppException(
            code="USER_INACTIVE",
            message="账号已停用，请联系超级管理员",
            status_code=403,
        )
    return user
