from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.models import AgentType, User, UserAgentPermission, UserRole
from app.schemas.user import MusicTaskQuotaResponse, UserResponse


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
        (
            permission.agent
            for permission in user.agent_permissions
            if user.role == UserRole.SUPER_ADMIN
            or permission.agent != AgentType.CRAWLER
        ),
        key=lambda agent: agent.value,
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        watermark_text=user.watermark_text or user.username,
        role=user.role,
        is_active=user.is_active,
        agent_permissions=permissions,
        music_quota=music_task_quota_response(user),
    )


def music_task_quota_response(user: User) -> MusicTaskQuotaResponse:
    is_unlimited = user.role == UserRole.SUPER_ADMIN
    return MusicTaskQuotaResponse(
        is_unlimited=is_unlimited,
        remaining_tasks=None if is_unlimited else user.music_quota_remaining,
        used_tasks=user.music_quota_used,
    )


def list_users(db: Session) -> list[UserResponse]:
    users = db.scalars(_user_query().order_by(User.id)).all()
    return [user_response(user) for user in users]


def create_member(
    db: Session,
    username: str,
    password: str,
    music_quota_remaining: int = 0,
) -> UserResponse:
    user = User(
        username=username.lower(),
        password_hash=hash_password(password),
        role=UserRole.MEMBER,
        music_quota_remaining=music_quota_remaining,
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
    if AgentType.CRAWLER in agents:
        raise AppException(
            code="PERMISSIONS_NOT_APPLICABLE",
            message="榜单采集仅限超级管理员，成员无需分配该权限",
            status_code=422,
        )

    user.agent_permissions.clear()
    user.agent_permissions.extend(
        UserAgentPermission(agent=agent) for agent in sorted(agents, key=str)
    )
    db.commit()
    return user_response(get_user_or_404(db, user_id))


def set_user_music_quota(
    db: Session,
    user_id: int,
    remaining_tasks: int,
) -> UserResponse:
    user = db.scalar(
        _user_query().where(User.id == user_id).with_for_update()
    )
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="用户不存在",
            status_code=404,
        )
    if user.role == UserRole.SUPER_ADMIN:
        raise AppException(
            code="MUSIC_QUOTA_NOT_APPLICABLE",
            message="超级管理员的音乐任务额度不受限制",
            status_code=409,
        )

    user.music_quota_remaining = remaining_tasks
    db.commit()
    return user_response(get_user_or_404(db, user_id))


def set_user_watermark(
    db: Session,
    user_id: int,
    watermark_text: str | None,
) -> UserResponse:
    user = get_user_or_404(db, user_id)
    user.watermark_text = watermark_text
    db.commit()
    return user_response(get_user_or_404(db, user_id))
