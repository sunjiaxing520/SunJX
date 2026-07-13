from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import BEARER_HEADERS, decode_access_token
from app.models import AgentType, User, UserAgentPermission, UserRole


bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def get_current_user(
    request: Request,
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            code="AUTH_TOKEN_MISSING",
            message="请先登录后再访问",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        )

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise AppException(
            code="AUTH_TOKEN_INVALID",
            message="登录凭证无效，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise AppException(
            code="AUTH_TOKEN_INVALID",
            message="登录凭证无效，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        )
    request.state.user_id = user.id
    if not user.is_active:
        raise AppException(
            code="USER_INACTIVE",
            message="账号已停用，请联系超级管理员",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if payload["ver"] != user.token_version:
        raise AppException(
            code="AUTH_TOKEN_REVOKED",
            message="登录凭证已失效，请重新登录",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=BEARER_HEADERS,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_super_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise AppException(
            code="PERMISSION_DENIED",
            message="没有超级管理员权限",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user


SuperAdmin = Annotated[User, Depends(require_super_admin)]


def require_agent_permission(agent: AgentType) -> Callable[..., User]:
    def dependency(current_user: CurrentUser, db: DatabaseSession) -> User:
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user

        permission = db.scalar(
            select(UserAgentPermission).where(
                UserAgentPermission.user_id == current_user.id,
                UserAgentPermission.agent == agent,
            )
        )
        if permission is None:
            raise AppException(
                code="AGENT_PERMISSION_DENIED",
                message=f"没有 {agent.value} Agent 的使用权限",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user

    return dependency
