import logging

from fastapi import APIRouter, Request, status

from app.api.dependencies import DatabaseSession, SuperAdmin
from app.core.logging import LOGGER_NAME
from app.core.request_context import get_request_id
from app.schemas.ai_provider import (
    AiProviderCreateRequest,
    AiProviderListResponse,
    AiProviderResponse,
    AiProviderTemplateResponse,
    AiProviderTestResponse,
    AiProviderUpdateRequest,
)
from app.services.ai_providers import (
    activate_ai_provider_config,
    create_ai_provider_config,
    delete_ai_provider_config,
    import_environment_ai_provider,
    list_ai_provider_configs,
    list_ai_provider_templates,
    test_ai_provider_config,
    update_ai_provider_config,
)


router = APIRouter(prefix="/ai-providers")
audit_logger = logging.getLogger(f"{LOGGER_NAME}.audit")


@router.get("/templates", response_model=list[AiProviderTemplateResponse])
def provider_templates(admin: SuperAdmin) -> list[AiProviderTemplateResponse]:
    return list_ai_provider_templates()


@router.get("", response_model=AiProviderListResponse)
def provider_configs(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderListResponse:
    return list_ai_provider_configs(db)


@router.post("", response_model=AiProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider_config(
    request: Request,
    payload: AiProviderCreateRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderResponse:
    provider = create_ai_provider_config(db, payload, user_id=admin.id)
    _audit(request, admin.id, "ai_provider_created", provider.id)
    return provider


@router.post("/import-environment", response_model=AiProviderResponse)
def import_environment_provider(
    request: Request,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderResponse:
    provider = import_environment_ai_provider(db, user_id=admin.id)
    _audit(request, admin.id, "ai_provider_environment_imported", provider.id)
    return provider


@router.put("/{config_id}", response_model=AiProviderResponse)
def update_provider_config(
    request: Request,
    config_id: int,
    payload: AiProviderUpdateRequest,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderResponse:
    provider = update_ai_provider_config(db, config_id, payload)
    _audit(request, admin.id, "ai_provider_updated", provider.id)
    return provider


@router.post("/{config_id}/test", response_model=AiProviderTestResponse)
def test_provider_config(
    request: Request,
    config_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderTestResponse:
    result = test_ai_provider_config(db, config_id)
    _audit(
        request,
        admin.id,
        "ai_provider_tested",
        config_id,
        test_status=result.status,
    )
    return result


@router.post("/{config_id}/activate", response_model=AiProviderResponse)
def activate_provider_config(
    request: Request,
    config_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> AiProviderResponse:
    provider = activate_ai_provider_config(db, config_id)
    _audit(request, admin.id, "ai_provider_activated", provider.id)
    return provider


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider_config(
    request: Request,
    config_id: int,
    db: DatabaseSession,
    admin: SuperAdmin,
) -> None:
    delete_ai_provider_config(db, config_id)
    _audit(request, admin.id, "ai_provider_deleted", config_id)


def _audit(
    request: Request,
    user_id: int,
    event: str,
    config_id: int,
    **extra,
) -> None:
    audit_logger.info(
        event,
        extra={
            "request_id": get_request_id(request),
            "user_id": user_id,
            "ai_provider_config_id": config_id,
            **extra,
        },
    )
