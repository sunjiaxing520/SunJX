from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.models import AgentType, User, UserAgentPermission, UserRole
from app.schemas.user import UserResponse


def _user_query():
    return select(User).options(selectinload(User.agent_permissions))


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(_user_query().where(User.id == user_id))
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="用户不存在",
            status_code=404,
        )
    return user


def user_response(user: User) -> UserResponse:
    permissions = sorted(
        (permission.agent for permission in user.agent_permissions),
        key=lambda agent: agent.value,
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        agent_permissions=permissions,
    )


def list_users(db: Session) -> list[UserResponse]:
    users = db.scalars(_user_query().order_by(User.id)).all()
    return [user_response(user) for user in users]


def create_member(db: Session, username: str, password: str) -> UserResponse:
    user = User(
        username=username.lower(),
        password_hash=hash_password(password),
        role=UserRole.MEMBER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            code="USERNAME_ALREADY_EXISTS",
            message="该登录账号已存在",
            status_code=409,
        ) from exc

    return user_response(get_user_or_404(db, user.id))


def set_user_status(
    db: Session,
    user_id: int,
    is_active: bool,
    actor_id: int,
) -> UserResponse:
    user = get_user_or_404(db, user_id)
    if user.id == actor_id and not is_active:
        raise AppException(
            code="CANNOT_DISABLE_SELF",
            message="超级管理员不能停用自己的账号",
            status_code=409,
        )

    user.is_active = is_active
    if not is_active:
        user.token_version += 1
    db.commit()
    return user_response(get_user_or_404(db, user_id))


def reset_user_password(db: Session, user_id: int, password: str) -> None:
    user = get_user_or_404(db, user_id)
    user.password_hash = hash_password(password)
    user.token_version += 1
    db.commit()


def replace_agent_permissions(
    db: Session,
    user_id: int,
    agents: set[AgentType],
) -> UserResponse:
    user = get_user_or_404(db, user_id)
    if user.role == UserRole.SUPER_ADMIN:
        raise AppException(
            code="PERMISSIONS_NOT_APPLICABLE",
            message="超级管理员默认拥有全部 Agent 权限",
            status_code=409,
        )

    user.agent_permissions.clear()
    user.agent_permissions.extend(
        UserAgentPermission(agent=agent) for agent in sorted(agents, key=str)
    )
    db.commit()
    return user_response(get_user_or_404(db, user_id))
