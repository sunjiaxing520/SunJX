from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


ApiUsageStatus = Literal["completed", "failed"]
BalanceStatus = Literal["available", "manual", "not_applicable", "hidden", "error"]


class ApiUsageResponse(BaseModel):
    id: int
    task_type: str
    task_id: int
    operation: str
    provider: str
    model: str | None
    method: str
    endpoint: str
    is_external: bool
    status: ApiUsageStatus
    external_request_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int
    usage_unit: str
    usage_quantity: float
    estimated_cost: float | None
    currency: str | None
    attempt_count: int
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime
    created_at: datetime


class ApiUsageMetrics(BaseModel):
    executions_today: int
    external_calls_today: int
    tokens_today: int
    tokens_7d: int


class DailyApiUsage(BaseModel):
    day: date
    executions: int
    external_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ProviderAccountUsage(BaseModel):
    provider: str
    display_name: str
    models: list[str]
    executions_today: int
    tokens_today: int
    tokens_7d: int
    usage_by_unit_7d: dict[str, float]
    balance_status: BalanceStatus
    balance_amount: float | None
    balance_unit: str | None
    balance_message: str
    console_url: str | None
    checked_at: datetime | None


class ApiUsageDashboard(BaseModel):
    metrics: ApiUsageMetrics
    daily: list[DailyApiUsage]
    providers: list[ProviderAccountUsage]
    recent_calls: list[ApiUsageResponse]
