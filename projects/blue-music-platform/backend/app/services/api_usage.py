from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.text_generation import ProviderCallMetadata
from app.core.config import settings
from app.core.time import APP_TIMEZONE, app_today, utc_day_bounds, utc_now
from app.models import AiProviderConfig, ApiUsageRecord
from app.schemas.api_usage import (
    ApiUsageDashboard,
    ApiUsageMetrics,
    ApiUsageResponse,
    DailyApiUsage,
    ProviderAccountUsage,
)


def api_usage_response(record: ApiUsageRecord) -> ApiUsageResponse:
    return ApiUsageResponse(
        id=record.id,
        task_type=record.task_type,
        task_id=record.task_id,
        operation=record.operation,
        provider=record.provider,
        model=record.model,
        method=record.method,
        endpoint=record.endpoint,
        is_external=record.is_external,
        status=record.status,
        external_request_id=record.external_request_id,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        total_tokens=record.total_tokens,
        cached_tokens=record.cached_tokens,
        usage_unit=record.usage_unit,
        usage_quantity=float(record.usage_quantity),
        estimated_cost=(
            float(record.estimated_cost)
            if record.estimated_cost is not None
            else None
        ),
        currency=record.currency,
        attempt_count=record.attempt_count,
        duration_ms=record.duration_ms,
        error_code=record.error_code,
        error_message=record.error_message,
        started_at=record.started_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
    )


def record_api_usage(
    db: Session,
    *,
    task_type: str,
    task_id: int,
    operation: str,
    provider: str,
    model: str | None,
    call: ProviderCallMetadata | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> ApiUsageRecord:
    metadata = call or fallback_text_call(provider, operation)
    record = ApiUsageRecord(
        task_type=task_type,
        task_id=task_id,
        operation=operation,
        provider=provider,
        model=model,
        method=metadata.method,
        endpoint=_safe_endpoint(metadata.endpoint),
        is_external=metadata.is_external,
        status=status,
        external_request_id=metadata.request_id,
        input_tokens=metadata.input_tokens,
        output_tokens=metadata.output_tokens,
        total_tokens=metadata.total_tokens,
        cached_tokens=metadata.cached_tokens,
        usage_unit=metadata.usage_unit,
        usage_quantity=Decimal(str(metadata.usage_quantity)),
        attempt_count=metadata.attempt_count,
        duration_ms=metadata.duration_ms,
        error_code=error_code,
        error_message=error_message,
        raw_usage=metadata.raw_usage,
        started_at=metadata.started_at,
        completed_at=metadata.completed_at,
    )
    db.add(record)
    return record


def fallback_text_call(provider: str, operation: str) -> ProviderCallMetadata:
    now = utc_now()
    if provider == "local":
        endpoint = f"local://rules-v1/{operation}"
        method = "EXECUTE"
        is_external = False
    else:
        base_url = settings.AI_BASE_URL or "unconfigured://text-provider"
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        method = "POST"
        is_external = False
    return ProviderCallMetadata(
        method=method,
        endpoint=endpoint,
        is_external=is_external,
        attempt_count=0,
        started_at=now,
        completed_at=now,
    )


def task_api_usage(
    db: Session, task_type: str, task_id: int
) -> list[ApiUsageResponse]:
    records = db.scalars(
        select(ApiUsageRecord)
        .where(
            ApiUsageRecord.task_type == task_type,
            ApiUsageRecord.task_id == task_id,
        )
        .order_by(ApiUsageRecord.created_at, ApiUsageRecord.id)
    ).all()
    return [api_usage_response(record) for record in records]


def get_api_usage_dashboard(
    db: Session, *, include_balance: bool
) -> ApiUsageDashboard:
    today = app_today()
    first_day = today - timedelta(days=6)
    period_start, _ = utc_day_bounds(first_day)
    records = list(
        db.scalars(
            select(ApiUsageRecord)
            .where(ApiUsageRecord.created_at >= period_start)
            .order_by(ApiUsageRecord.created_at, ApiUsageRecord.id)
        ).all()
    )
    recent = db.scalars(
        select(ApiUsageRecord)
        .order_by(ApiUsageRecord.created_at.desc(), ApiUsageRecord.id.desc())
        .limit(15)
    ).all()

    day_records: dict[date, list[ApiUsageRecord]] = defaultdict(list)
    for record in records:
        local_day = _app_date(record.created_at)
        day_records[local_day].append(record)

    daily: list[DailyApiUsage] = []
    for offset in range(7):
        day = first_day + timedelta(days=offset)
        items = day_records[day]
        daily.append(
            DailyApiUsage(
                day=day,
                executions=len(items),
                external_calls=sum(record.is_external for record in items),
                input_tokens=sum(record.input_tokens for record in items),
                output_tokens=sum(record.output_tokens for record in items),
                total_tokens=sum(record.total_tokens for record in items),
            )
        )

    today_items = day_records[today]
    provider_records: dict[str, list[ApiUsageRecord]] = defaultdict(list)
    for record in records:
        provider_records[_canonical_provider(record.provider, record.endpoint)].append(record)
    active_config = db.scalar(
        select(AiProviderConfig)
        .where(AiProviderConfig.is_active.is_(True))
        .order_by(AiProviderConfig.updated_at.desc(), AiProviderConfig.id.desc())
        .limit(1)
    )
    active_provider = active_config.template_key if active_config else settings.AI_PROVIDER
    provider_records.setdefault(active_provider, [])
    active_endpoint: str | None = None
    active_model: str | None = None
    if active_config:
        active_endpoint = (
            "local://rules-v1"
            if active_config.protocol == "local"
            else f"{active_config.base_url.rstrip('/')}/chat/completions"
        )
        active_model = active_config.model

    providers = [
        _provider_summary(
            provider,
            items,
            today=today,
            include_balance=include_balance,
            configured_endpoint=active_endpoint if provider == active_provider else None,
            configured_model=active_model if provider == active_provider else None,
        )
        for provider, items in sorted(provider_records.items())
    ]

    return ApiUsageDashboard(
        metrics=ApiUsageMetrics(
            executions_today=len(today_items),
            external_calls_today=sum(record.is_external for record in today_items),
            tokens_today=sum(record.total_tokens for record in today_items),
            tokens_7d=sum(record.total_tokens for record in records),
        ),
        daily=daily,
        providers=providers,
        recent_calls=[api_usage_response(record) for record in recent],
    )


def _provider_summary(
    provider: str,
    records: list[ApiUsageRecord],
    *,
    today,
    include_balance: bool,
    configured_endpoint: str | None,
    configured_model: str | None,
) -> ProviderAccountUsage:
    today_records = [
        record
        for record in records
        if _app_date(record.created_at) == today
    ]
    units: dict[str, float] = defaultdict(float)
    for record in records:
        units[record.usage_unit] += float(record.usage_quantity)

    endpoint = records[-1].endpoint if records else configured_endpoint or _configured_endpoint(provider)
    display_name, console_url = _provider_identity(provider, endpoint)
    if provider == "local":
        balance_status = "not_applicable"
        balance_message = "本地规则执行不消耗第三方账户余额"
    elif not include_balance:
        balance_status = "hidden"
        balance_message = "仅超级管理员可查看账户余额"
        console_url = None
    else:
        balance_status = "manual"
        balance_message = "当前供应商未接入自动余额查询，请前往供应商控制台查看"

    model_names = {record.model for record in records if record.model}
    if configured_model:
        model_names.add(configured_model)
    elif provider == settings.AI_PROVIDER and settings.AI_MODEL:
        model_names.add(settings.AI_MODEL)
    models = sorted(model_names)
    return ProviderAccountUsage(
        provider=provider,
        display_name=display_name,
        models=models,
        executions_today=len(today_records),
        tokens_today=sum(record.total_tokens for record in today_records),
        tokens_7d=sum(record.total_tokens for record in records),
        usage_by_unit_7d=dict(units),
        balance_status=balance_status,
        balance_amount=None,
        balance_unit=None,
        balance_message=balance_message,
        console_url=console_url,
        checked_at=None,
    )


def _configured_endpoint(provider: str) -> str:
    if provider == "local":
        return "local://rules-v1"
    if provider == settings.AI_PROVIDER and settings.AI_BASE_URL:
        return f"{settings.AI_BASE_URL}/chat/completions"
    return ""


def _provider_identity(provider: str, endpoint: str) -> tuple[str, str | None]:
    hostname = (urlparse(endpoint).hostname or "").lower()
    if provider == "local":
        return "本地规则基线", None
    if provider == "bigmodel":
        return "智谱 BigModel", "https://bigmodel.cn/"
    if provider == "deepseek":
        return "DeepSeek", "https://platform.deepseek.com/"
    if provider == "qwen":
        return "阿里百炼 Qwen", "https://bailian.console.aliyun.com/"
    if provider == "minimax":
        return "MiniMax", "https://platform.minimaxi.com/"
    if provider == "suno":
        return "Suno", "https://platform.suno.com/"
    if hostname.endswith("bigmodel.cn"):
        return "智谱 BigModel", "https://bigmodel.cn/"
    if hostname.endswith("mureka.ai"):
        return "Mureka", "https://platform.mureka.ai/"
    if hostname.endswith("minimaxi.com"):
        return "MiniMax", "https://platform.minimaxi.com/"
    if hostname.endswith("suno.com"):
        return "Suno", "https://platform.suno.com/"
    return provider, None


def _canonical_provider(provider: str, endpoint: str) -> str:
    if provider == "local":
        return provider
    hostname = (urlparse(endpoint).hostname or "").lower()
    if hostname.endswith("bigmodel.cn"):
        return "bigmodel"
    if hostname.endswith("deepseek.com"):
        return "deepseek"
    if hostname.endswith("aliyuncs.com"):
        return "qwen"
    if hostname.endswith("minimaxi.com"):
        return "minimax"
    if hostname.endswith("suno.com"):
        return "suno"
    return provider


def _app_date(value: datetime) -> date:
    aware_value = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware_value.astimezone(APP_TIMEZONE).date()


def _safe_endpoint(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    if parts.scheme not in {"http", "https"}:
        return endpoint.split("?", 1)[0].split("#", 1)[0]
    hostname = parts.hostname or ""
    netloc = f"{hostname}:{parts.port}" if parts.port else hostname
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
