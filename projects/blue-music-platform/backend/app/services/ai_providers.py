from datetime import datetime, timezone
from urllib.parse import urlparse, urlsplit

from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.adapters.text_generation import (
    ProviderCallMetadata,
    TextGenerationProvider,
    TextProviderConfig,
    TextProviderError,
    create_text_provider,
    get_text_provider,
)
from app.core.ai_provider_templates import (
    AI_PROVIDER_TEMPLATES,
    AiProviderTemplate,
    get_ai_provider_template,
)
from app.core.config import settings
from app.core.credential_crypto import (
    CredentialDecryptionError,
    credential_hint,
    decrypt_credential,
    encrypt_credential,
)
from app.core.exceptions import AppException
from app.core.time import utc_now
from app.models import AiProviderConfig, TaskStatus
from app.schemas.ai_provider import (
    AiProviderCreateRequest,
    AiProviderListResponse,
    AiProviderResponse,
    AiProviderTemplateResponse,
    AiProviderTestResponse,
    AiProviderUpdateRequest,
    EnvironmentAiProviderResponse,
)
from app.services.api_usage import api_usage_response, record_api_usage


def list_ai_provider_templates() -> list[AiProviderTemplateResponse]:
    return [AiProviderTemplateResponse(**template.__dict__) for template in AI_PROVIDER_TEMPLATES]


def list_ai_provider_configs(db: Session) -> AiProviderListResponse:
    items = db.scalars(
        select(AiProviderConfig).order_by(
            AiProviderConfig.is_active.desc(),
            AiProviderConfig.updated_at.desc(),
            AiProviderConfig.id.desc(),
        )
    ).all()
    return AiProviderListResponse(
        items=[ai_provider_response(item) for item in items],
        runtime_source="database" if any(item.is_active for item in items) else "environment",
        environment_fallback=environment_ai_provider_response(),
    )


def create_ai_provider_config(
    db: Session,
    payload: AiProviderCreateRequest,
    *,
    user_id: int,
    source: str = "manual",
) -> AiProviderResponse:
    template = _require_template(payload.template_key)
    _ensure_unique_name(db, payload.name)
    api_key = _secret_value(payload.api_key)
    values = _connection_values(
        template=template,
        base_url=payload.base_url,
        model=payload.model,
        api_key=api_key,
        existing_api_key=None,
        existing_api_hint=None,
    )
    config = AiProviderConfig(
        name=payload.name,
        template_key=template.key,
        protocol=template.protocol,
        base_url=values["base_url"],
        api_key_encrypted=values["api_key_encrypted"],
        api_key_hint=values["api_key_hint"],
        model=values["model"],
        supports_json_mode=(
            payload.supports_json_mode
            if payload.supports_json_mode is not None
            else template.supports_json_mode
        ),
        max_tokens_parameter=(
            payload.max_tokens_parameter
            or template.max_tokens_parameter
        ),
        request_timeout_seconds=payload.request_timeout_seconds,
        max_retries=payload.max_retries,
        analysis_max_output_tokens=payload.analysis_max_output_tokens,
        lyrics_max_output_tokens=payload.lyrics_max_output_tokens,
        source=source,
        created_by_id=user_id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return ai_provider_response(config)


def update_ai_provider_config(
    db: Session,
    config_id: int,
    payload: AiProviderUpdateRequest,
) -> AiProviderResponse:
    config = _require_config(db, config_id)
    if config.is_active:
        raise AppException(
            code="AI_PROVIDER_ACTIVE_EDIT_FORBIDDEN",
            message="当前使用中的接口不能直接编辑，请先启用另一个接口",
            status_code=409,
        )
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != config.name:
        _ensure_unique_name(db, changes["name"], exclude_id=config.id)

    template = _require_template(changes.get("template_key", config.template_key))
    api_key = _secret_value(payload.api_key) if "api_key" in changes else None
    values = _connection_values(
        template=template,
        base_url=changes.get("base_url", config.base_url),
        model=changes.get("model", config.model),
        api_key=api_key,
        existing_api_key=config.api_key_encrypted,
        existing_api_hint=config.api_key_hint,
    )
    config.name = changes.get("name", config.name)
    config.template_key = template.key
    config.protocol = template.protocol
    config.base_url = values["base_url"]
    config.api_key_encrypted = values["api_key_encrypted"]
    config.api_key_hint = values["api_key_hint"]
    config.model = values["model"]
    config.supports_json_mode = changes.get(
        "supports_json_mode", config.supports_json_mode
    )
    config.max_tokens_parameter = changes.get(
        "max_tokens_parameter", config.max_tokens_parameter
    )
    for field_name in (
        "request_timeout_seconds",
        "max_retries",
        "analysis_max_output_tokens",
        "lyrics_max_output_tokens",
    ):
        if field_name in changes:
            setattr(config, field_name, changes[field_name])
    config.last_test_status = "untested"
    config.last_test_message = None
    config.last_tested_at = None
    db.commit()
    db.refresh(config)
    return ai_provider_response(config)


def delete_ai_provider_config(db: Session, config_id: int) -> None:
    config = _require_config(db, config_id)
    if config.is_active:
        raise AppException(
            code="AI_PROVIDER_ACTIVE_DELETE_FORBIDDEN",
            message="当前使用中的接口不能删除",
            status_code=409,
        )
    db.delete(config)
    db.commit()


def test_ai_provider_config(db: Session, config_id: int) -> AiProviderTestResponse:
    config = _require_config(db, config_id)
    provider_name = config.template_key
    model = config.model
    try:
        provider = _provider_from_record(config)
        result = provider.test_connection()
        status = "success"
        message = "连接成功，接口已返回有效 JSON"
        call = result.call
    except TextProviderError as exc:
        status = "failed"
        message = str(exc)
        call = exc.call or _unattempted_call(config)

    config.last_test_status = status
    config.last_test_message = message
    config.last_tested_at = utc_now()
    usage = record_api_usage(
        db,
        task_type="provider_test",
        task_id=config.id,
        operation="provider.test",
        provider=provider_name,
        model=model,
        call=call,
        status=(
            TaskStatus.COMPLETED.value
            if status == "success"
            else TaskStatus.FAILED.value
        ),
        error_code=None if status == "success" else "AI_PROVIDER_TEST_FAILED",
        error_message=None if status == "success" else message,
    )
    db.commit()
    db.refresh(config)
    db.refresh(usage)
    return AiProviderTestResponse(
        status=status,
        message=message,
        provider=ai_provider_response(config),
        api_usage=api_usage_response(usage),
    )


def activate_ai_provider_config(db: Session, config_id: int) -> AiProviderResponse:
    config = _require_config(db, config_id)
    if config.last_test_status != "success":
        raise AppException(
            code="AI_PROVIDER_TEST_REQUIRED",
            message="请先完成连接测试，测试成功后才能启用",
            status_code=409,
        )
    db.execute(
        update(AiProviderConfig)
        .where(AiProviderConfig.id != config.id)
        .values(is_active=False)
    )
    config.is_active = True
    db.commit()
    db.refresh(config)
    return ai_provider_response(config)


def import_environment_ai_provider(
    db: Session,
    *,
    user_id: int,
) -> AiProviderResponse:
    existing = db.scalar(
        select(AiProviderConfig)
        .where(AiProviderConfig.source == "environment")
        .order_by(AiProviderConfig.id.desc())
        .limit(1)
    )
    if existing is not None:
        return ai_provider_response(existing)

    template = _environment_template()
    display_name = f"{template.display_name}（环境导入）"
    payload = AiProviderCreateRequest(
        name=_available_name(db, display_name),
        template_key=template.key,
        base_url=settings.AI_BASE_URL or template.default_base_url,
        model=(
            "rules-v1"
            if settings.AI_PROVIDER == "local"
            else settings.AI_MODEL or template.default_model
        ),
        api_key=(SecretStr(settings.AI_API_KEY) if settings.AI_API_KEY else None),
        supports_json_mode=template.supports_json_mode,
        max_tokens_parameter=template.max_tokens_parameter,
        request_timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
        analysis_max_output_tokens=settings.AI_ANALYSIS_MAX_OUTPUT_TOKENS,
        lyrics_max_output_tokens=settings.AI_LYRICS_MAX_OUTPUT_TOKENS,
    )
    return create_ai_provider_config(
        db,
        payload,
        user_id=user_id,
        source="environment",
    )


def resolve_text_provider(db: Session) -> TextGenerationProvider:
    config = db.scalar(
        select(AiProviderConfig)
        .where(AiProviderConfig.is_active.is_(True))
        .order_by(AiProviderConfig.updated_at.desc(), AiProviderConfig.id.desc())
        .limit(1)
    )
    if config is None:
        return get_text_provider()
    return _provider_from_record(config)


def ai_provider_response(config: AiProviderConfig) -> AiProviderResponse:
    template = get_ai_provider_template(config.template_key)
    return AiProviderResponse(
        id=config.id,
        name=config.name,
        template_key=config.template_key,
        template_name=template.display_name if template else config.template_key,
        protocol=config.protocol,
        base_url=config.base_url,
        endpoint=_endpoint(config.protocol, config.base_url),
        model=config.model,
        has_api_key=bool(config.api_key_encrypted),
        api_key_hint=config.api_key_hint,
        supports_json_mode=config.supports_json_mode,
        max_tokens_parameter=config.max_tokens_parameter,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
        analysis_max_output_tokens=config.analysis_max_output_tokens,
        lyrics_max_output_tokens=config.lyrics_max_output_tokens,
        is_active=config.is_active,
        source=config.source,
        last_test_status=config.last_test_status,
        last_test_message=config.last_test_message,
        last_tested_at=config.last_tested_at,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def environment_ai_provider_response() -> EnvironmentAiProviderResponse:
    template = _environment_template()
    base_url = settings.AI_BASE_URL or template.default_base_url
    api_key = settings.AI_API_KEY
    return EnvironmentAiProviderResponse(
        configured=(
            settings.AI_PROVIDER == "local"
            or bool(base_url and settings.AI_MODEL and api_key)
        ),
        template_key=template.key,
        template_name=template.display_name,
        base_url=base_url,
        endpoint=_endpoint(template.protocol, base_url),
        model=(
            "rules-v1"
            if settings.AI_PROVIDER == "local"
            else settings.AI_MODEL or template.default_model
        ),
        has_api_key=bool(api_key),
        api_key_hint=credential_hint(api_key) if api_key else None,
    )


def _provider_from_record(config: AiProviderConfig) -> TextGenerationProvider:
    try:
        api_key = (
            decrypt_credential(config.api_key_encrypted)
            if config.api_key_encrypted
            else ""
        )
    except CredentialDecryptionError as exc:
        raise TextProviderError(str(exc)) from exc
    return create_text_provider(
        TextProviderConfig(
            template_key=config.template_key,
            protocol=config.protocol,
            base_url=config.base_url,
            api_key=api_key,
            model=config.model,
            supports_json_mode=config.supports_json_mode,
            max_tokens_parameter=config.max_tokens_parameter,
            request_timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
            analysis_max_output_tokens=config.analysis_max_output_tokens,
            lyrics_max_output_tokens=config.lyrics_max_output_tokens,
        )
    )


def _connection_values(
    *,
    template: AiProviderTemplate,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    existing_api_key: str | None,
    existing_api_hint: str | None,
) -> dict[str, str | None]:
    if template.protocol == "local":
        return {
            "base_url": "",
            "model": "rules-v1",
            "api_key_encrypted": None,
            "api_key_hint": None,
        }
    normalized_url = _validate_base_url(base_url or template.default_base_url)
    normalized_model = (model or template.default_model).strip()
    if not normalized_model:
        raise AppException(
            code="AI_PROVIDER_MODEL_REQUIRED",
            message="请输入模型名称",
            status_code=422,
        )
    if api_key:
        encrypted = encrypt_credential(api_key)
        hint = credential_hint(api_key)
    elif existing_api_key:
        encrypted = existing_api_key
        hint = existing_api_hint
    else:
        raise AppException(
            code="AI_PROVIDER_API_KEY_REQUIRED",
            message="请输入 API Key",
            status_code=422,
        )
    return {
        "base_url": normalized_url,
        "model": normalized_model,
        "api_key_encrypted": encrypted,
        "api_key_hint": hint,
    }


def _validate_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parts = urlsplit(normalized)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise AppException(
            code="AI_PROVIDER_BASE_URL_INVALID",
            message="Base URL 必须是无账号、查询参数和片段的 HTTP(S) 地址",
            status_code=422,
        )
    if parts.path.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    return normalized.rstrip("/")


def _require_template(key: str) -> AiProviderTemplate:
    template = get_ai_provider_template(key)
    if template is None:
        raise AppException(
            code="AI_PROVIDER_TEMPLATE_NOT_FOUND",
            message="AI 接口模板不存在",
            status_code=404,
        )
    return template


def _require_config(db: Session, config_id: int) -> AiProviderConfig:
    config = db.get(AiProviderConfig, config_id)
    if config is None:
        raise AppException(
            code="AI_PROVIDER_NOT_FOUND",
            message="AI 接口配置不存在",
            status_code=404,
        )
    return config


def _ensure_unique_name(
    db: Session,
    name: str,
    *,
    exclude_id: int | None = None,
) -> None:
    query = select(AiProviderConfig.id).where(
        func.lower(AiProviderConfig.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(AiProviderConfig.id != exclude_id)
    if db.scalar(query) is not None:
        raise AppException(
            code="AI_PROVIDER_NAME_EXISTS",
            message="接口配置名称已存在",
            status_code=409,
        )


def _available_name(db: Session, base_name: str) -> str:
    name = base_name
    suffix = 2
    while db.scalar(
        select(AiProviderConfig.id).where(func.lower(AiProviderConfig.name) == name.lower())
    ) is not None:
        name = f"{base_name} {suffix}"
        suffix += 1
    return name


def _environment_template() -> AiProviderTemplate:
    if settings.AI_PROVIDER == "local":
        return _require_template("local")
    hostname = (urlparse(settings.AI_BASE_URL).hostname or "").lower()
    key = "openai_compatible"
    if hostname.endswith("bigmodel.cn"):
        key = "bigmodel"
    elif hostname.endswith("deepseek.com"):
        key = "deepseek"
    elif hostname.endswith("aliyuncs.com"):
        key = "qwen"
    elif hostname.endswith("minimaxi.com"):
        key = "minimax"
    return _require_template(key)


def _endpoint(protocol: str, base_url: str) -> str:
    return "local://rules-v1" if protocol == "local" else f"{base_url.rstrip('/')}/chat/completions"


def _unattempted_call(config: AiProviderConfig) -> ProviderCallMetadata:
    now = datetime.now(timezone.utc)
    return ProviderCallMetadata(
        method="EXECUTE" if config.protocol == "local" else "POST",
        endpoint=_endpoint(config.protocol, config.base_url),
        is_external=False,
        attempt_count=0,
        started_at=now,
        completed_at=now,
    )


def _secret_value(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None
