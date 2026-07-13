import logging

from fastapi import APIRouter, Request, status

from app.api.dependencies import DatabaseSession, SuperAdmin
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.schemas.user import (
    AgentPermissionsUpdate,
    CreateUserRequest,
    UserPasswordResetRequest,
    UserResponse,
    UserStatusUpdate,
)
from app.services.users import (
    create_member,
    list_users,
    replace_agent_permissions,
    reset_user_password,
    set_user_status,
)


router = APIRouter(prefix="/users")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.get("", response_model=list[UserResponse])
def users_list(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> list[UserResponse]:
    return list_users(db)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: Request,
    payload: CreateUserRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> UserResponse:
    user = create_member(
        db,
        username=payload.username,
        password=payload.password.get_secret_value(),
    )
    audit_logger.info(
        "member_created",
        extra={
            "request_id": get_request_id(request),
            "user_id": admin.id,
            "target_user_id": user.id,
        },
    )
    return user


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    request: Request,
    user_id: int,
    payload: UserStatusUpdate,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> UserResponse:
    user = set_user_status(db, user_id, payload.is_active, admin.id)
    audit_logger.info(
        "user_status_changed",
        extra={
            "request_id": get_request_id(request),
            "user_id": admin.id,
            "target_user_id": user_id,
        },
    )
    return user


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def update_user_password(
    request: Request,
    user_id: int,
    payload: UserPasswordResetRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> None:
    reset_user_password(db, user_id, payload.password.get_secret_value())
    audit_logger.info(
        "user_password_reset",
        extra={
            "request_id": get_request_id(request),
            "user_id": admin.id,
            "target_user_id": user_id,
        },
    )


@router.put("/{user_id}/agent-permissions", response_model=UserResponse)
def update_agent_permissions(
    request: Request,
    user_id: int,
    payload: AgentPermissionsUpdate,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> UserResponse:
    user = replace_agent_permissions(db, user_id, payload.agents)
    audit_logger.info(
        "agent_permissions_changed",
        extra={
            "request_id": get_request_id(request),
            "user_id": admin.id,
            "target_user_id": user_id,
        },
    )
    return user
