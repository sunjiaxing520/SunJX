from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

from app.schemas.api_usage import ApiUsageResponse


MaxTokensParameter = Literal["max_tokens", "max_completion_tokens"]
ProviderTestStatus = Literal["untested", "success", "failed"]


class AiProviderTemplateResponse(BaseModel):
    key: str
    display_name: str
    protocol: str
    description: str
    default_base_url: str
    default_model: str
    requires_api_key: bool
    supports_json_mode: bool
    max_tokens_parameter: MaxTokensParameter
    console_url: str | None
    docs_url: str | None


class AiProviderCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    template_key: str = Field(min_length=2, max_length=40)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=120)
    api_key: SecretStr | None = Field(default=None, min_length=4, max_length=1000)
    supports_json_mode: bool | None = None
    max_tokens_parameter: MaxTokensParameter | None = None
    request_timeout_seconds: float = Field(default=180, ge=5, le=600)
    max_retries: int = Field(default=2, ge=1, le=5)
    analysis_max_output_tokens: int = Field(default=2500, ge=128, le=100000)
    lyrics_max_output_tokens: int = Field(default=3500, ge=128, le=100000)

    @field_validator("name", "base_url", "model")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AiProviderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    template_key: str | None = Field(default=None, min_length=2, max_length=40)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=120)
    api_key: SecretStr | None = Field(default=None, min_length=4, max_length=1000)
    supports_json_mode: bool | None = None
    max_tokens_parameter: MaxTokensParameter | None = None
    request_timeout_seconds: float | None = Field(default=None, ge=5, le=600)
    max_retries: int | None = Field(default=None, ge=1, le=5)
    analysis_max_output_tokens: int | None = Field(
        default=None, ge=128, le=100000
    )
    lyrics_max_output_tokens: int | None = Field(default=None, ge=128, le=100000)

    @field_validator("name", "base_url", "model")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AiProviderResponse(BaseModel):
    id: int
    name: str
    template_key: str
    template_name: str
    protocol: str
    base_url: str
    endpoint: str
    model: str
    has_api_key: bool
    api_key_hint: str | None
    supports_json_mode: bool
    max_tokens_parameter: MaxTokensParameter
    request_timeout_seconds: float
    max_retries: int
    analysis_max_output_tokens: int
    lyrics_max_output_tokens: int
    is_active: bool
    source: str
    last_test_status: ProviderTestStatus
    last_test_message: str | None
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnvironmentAiProviderResponse(BaseModel):
    configured: bool
    template_key: str
    template_name: str
    base_url: str
    endpoint: str
    model: str
    has_api_key: bool
    api_key_hint: str | None


class AiProviderListResponse(BaseModel):
    items: list[AiProviderResponse]
    runtime_source: Literal["database", "environment"]
    environment_fallback: EnvironmentAiProviderResponse


class AiProviderTestResponse(BaseModel):
    status: Literal["success", "failed"]
    message: str
    provider: AiProviderResponse
    api_usage: ApiUsageResponse
