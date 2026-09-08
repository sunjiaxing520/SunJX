from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx

from app.adapters.text_generation import ProviderCallMetadata
from app.core.config import settings
from app.core.time import utc_now


MusicProviderImplementation = Literal[
    "official", "sunoapi_org", "compatibility"
]


class MusicProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "SUNO_PROVIDER_FAILED",
        call: ProviderCallMetadata | None = None,
        detail: dict[str, object] | None = None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        requires_human: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.call = call
        self.detail = detail
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.requires_human = requires_human


class MusicProviderPending(MusicProviderError):
    def __init__(
        self,
        *,
        external_task_id: str,
        provider_status: str,
        call: ProviderCallMetadata,
        retry_after_seconds: float,
        submitted_now: bool = False,
    ) -> None:
        super().__init__(
            "Suno 音乐任务仍在处理，系统将等待回调并定时查询",
            code="SUNOAPI_TASK_PENDING",
            call=call,
            detail={
                "external_task_id": external_task_id,
                "provider_status": provider_status,
            },
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )
        self.external_task_id = external_task_id
        self.provider_status = provider_status
        self.submitted_now = submitted_now


@dataclass(frozen=True)
class MusicGenerationInput:
    title: str
    lyrics: str
    style_prompt: str
    instrumental: bool
    negative_tags: list[str]
    requirements: str | None
    style_tags: list[str] = field(default_factory=list)
    source_external_id: str | None = None


@dataclass(frozen=True)
class MusicTrackOutput:
    external_id: str
    title: str
    audio_url: str
    media_type: str = "audio/mpeg"
    duration_seconds: int | None = None
    image_url: str | None = None
    provider_page_url: str | None = None


@dataclass(frozen=True)
class MusicGenerationOutput:
    external_task_id: str
    provider_status: str
    tracks: list[MusicTrackOutput]
    call: ProviderCallMetadata


@dataclass(frozen=True)
class MusicProviderQuota:
    credits_remaining: float | None
    usage: float | None
    limit: float | None
    period: str | None
    raw: dict[str, Any]
    call: ProviderCallMetadata


class MusicGenerationProvider(Protocol):
    name: str
    implementation: MusicProviderImplementation
    model: str | None

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput: ...

    def resume(
        self,
        payload: MusicGenerationInput,
        external_task_id: str,
    ) -> MusicGenerationOutput: ...

    def get_quota(self) -> MusicProviderQuota: ...


class SunoOfficialMusicProvider:
    """Fail-closed official adapter until the account-specific contract is available."""

    name = "suno"
    implementation: MusicProviderImplementation = "official"

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or settings.SUNO_MODEL or None
        if not settings.SUNO_API_BASE_URL or not settings.SUNO_API_KEY:
            raise MusicProviderError(
                "尚未配置 Suno 官方 API。请先在 Suno Platform 获得正式访问权限和密钥",
                code="SUNO_API_NOT_CONFIGURED",
                detail={"platform_url": "https://platform.suno.com/"},
            )

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        raise self._contract_pending()

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        raise self._contract_pending()

    def resume(
        self,
        payload: MusicGenerationInput,
        external_task_id: str,
    ) -> MusicGenerationOutput:
        raise self._contract_pending()

    def get_quota(self) -> MusicProviderQuota:
        raise self._contract_pending()

    @staticmethod
    def _contract_pending() -> MusicProviderError:
        return MusicProviderError(
            "Suno 官方 API 已配置，但账号内正式接口文档尚未完成合同映射",
            code="SUNO_API_CONTRACT_PENDING",
            detail={"platform_url": "https://platform.suno.com/"},
        )


class SunoApiOrgMusicProvider:
    """Documented async adapter for the third-party sunoapi.org service."""

    name = "suno"
    implementation: MusicProviderImplementation = "sunoapi_org"
    _pending_statuses = {"PENDING", "TEXT_SUCCESS", "FIRST_SUCCESS"}
    _failed_statuses = {
        "CREATE_TASK_FAILED",
        "GENERATE_AUDIO_FAILED",
        "CALLBACK_EXCEPTION",
        "SENSITIVE_WORD_ERROR",
    }

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        callback_url: str | None = None,
        model: str | None = None,
        on_submitted: Callable[[str], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.SUNOAPI_ORG_API_KEY
        self.base_url = (
            base_url if base_url is not None else settings.SUNOAPI_ORG_BASE_URL
        ).rstrip("/")
        self.callback_url = (
            callback_url
            if callback_url is not None
            else settings.SUNOAPI_ORG_CALLBACK_BASE_URL
        ).rstrip("/")
        self.model = model or settings.SUNO_MODEL or "v4.5"
        self._on_submitted = on_submitted
        self._validate_connection_settings()
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"blue-music-platform/{settings.VERSION}",
            },
            timeout=settings.SUNO_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _submission_unknown(self, call: ProviderCallMetadata | None = None) -> MusicProviderError:
        return MusicProviderError(
            "生成请求已发出但未确认任务编号；已暂停，请先在供应商后台核对，避免重复扣费",
            code="SUNOAPI_SUBMISSION_UNKNOWN",
            call=call,
        )

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        self._validate_callback_url()
        model = self._provider_model()
        style = self._style_tags(payload)
        self._validate_generation_payload(payload, model=model, style=style)
        request_payload: dict[str, Any] = {
            "customMode": True,
            "instrumental": payload.instrumental,
            "model": model,
            "callBackUrl": self.callback_url,
            "style": style,
            "title": payload.title,
        }
        if not payload.instrumental:
            request_payload["prompt"] = payload.lyrics
        if payload.negative_tags:
            request_payload["negativeTags"] = ", ".join(payload.negative_tags)

        started_at = utc_now()
        response = self._request(
            "POST",
            "/api/v1/generate",
            started_at=started_at,
            json=request_payload,
        )
        body = self._require_success_body(
            response,
            method="POST",
            path="/api/v1/generate",
            started_at=started_at,
        )
        data = body.get("data")
        external_task_id = (
            str(data.get("taskId") or "").strip()
            if isinstance(data, dict)
            else ""
        )
        if not external_task_id or len(external_task_id) > 200:
            raise self._submission_unknown(
                call=self._call_metadata(
                    response,
                    method="POST",
                    path="/api/v1/generate",
                    started_at=started_at,
                    completed_at=utc_now(),
                ),
            )
        if self._on_submitted is not None:
            self._on_submitted(external_task_id)
        raise MusicProviderPending(
            external_task_id=external_task_id,
            provider_status="submitted",
            submitted_now=True,
            retry_after_seconds=max(5.0, settings.SUNO_POLL_INTERVAL_SECONDS),
            call=self._call_metadata(
                response,
                method="POST",
                path="/api/v1/generate",
                started_at=started_at,
                completed_at=utc_now(),
                usage_unit="generation_requests",
                usage_quantity=1,
                raw_usage={
                    "implementation": self.implementation,
                    "operation": "generate",
                    "expected_track_count": 2,
                },
            ),
        )

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        raise MusicProviderError(
            "当前 SunoAPI 接入仅开放完整音乐生成，暂不支持续写或改编",
            code="SUNOAPI_OPERATION_NOT_SUPPORTED",
        )

    def resume(
        self,
        payload: MusicGenerationInput,
        external_task_id: str,
    ) -> MusicGenerationOutput:
        task_id = external_task_id.strip()
        if not task_id or len(task_id) > 200:
            raise MusicProviderError(
                "SunoAPI 外部任务编号无效，无法继续查询",
                code="SUNO_EXTERNAL_TASK_INVALID",
            )
        started_at = utc_now()
        path = "/api/v1/generate/record-info"
        response = self._request(
            "GET",
            path,
            started_at=started_at,
            params={"taskId": task_id},
        )
        body = self._require_success_body(
            response,
            method="GET",
            path=path,
            started_at=started_at,
        )
        data = body.get("data")
        if not isinstance(data, dict):
            raise MusicProviderError(
                "SunoAPI 任务详情缺少 data 对象",
                code="SUNOAPI_INVALID_RESPONSE",
            )
        returned_task_id = str(data.get("taskId") or task_id).strip()
        if returned_task_id != task_id:
            raise MusicProviderError(
                "SunoAPI 返回了与当前任务不一致的任务编号",
                code="SUNO_EXTERNAL_TASK_CONFLICT",
                detail={
                    "expected_external_task_id": task_id,
                    "received_external_task_id": returned_task_id,
                },
            )
        provider_status = str(data.get("status") or "").strip().upper()
        completed_at = utc_now()
        call = self._call_metadata(
            response,
            method="GET",
            path=path,
            started_at=started_at,
            completed_at=completed_at,
            usage_unit="status_checks",
            usage_quantity=1,
            raw_usage={
                "implementation": self.implementation,
                "operation": "resume",
                "provider_status": provider_status,
            },
        )
        if provider_status in self._pending_statuses:
            raise MusicProviderPending(
                external_task_id=task_id,
                provider_status=provider_status.lower(),
                retry_after_seconds=max(5.0, settings.SUNO_POLL_INTERVAL_SECONDS),
                call=call,
            )
        if provider_status in self._failed_statuses:
            error_message = str(
                data.get("errorMessage") or "SunoAPI 音乐生成失败"
            ).strip()
            raise MusicProviderError(
                error_message,
                code=(
                    "SUNOAPI_SENSITIVE_CONTENT"
                    if provider_status == "SENSITIVE_WORD_ERROR"
                    else "SUNOAPI_GENERATION_FAILED"
                ),
                call=call,
                detail={
                    "provider_status": provider_status,
                    "provider_error_code": data.get("errorCode"),
                },
            )
        if provider_status != "SUCCESS":
            raise MusicProviderError(
                "SunoAPI 返回了未知的任务状态",
                code="SUNOAPI_INVALID_RESPONSE",
                retryable=True,
                call=call,
            )

        provider_response = data.get("response")
        items = (
            provider_response.get("sunoData")
            if isinstance(provider_response, dict)
            else None
        )
        if not isinstance(items, list) or not items:
            raise MusicProviderError(
                "SunoAPI 任务已完成，但没有返回音乐结果",
                code="SUNO_NO_AUDIO_RESULT",
                call=call,
                retryable=True,
                detail={"external_task_id": task_id},
            )
        tracks = [self._track_output(item) for item in items if isinstance(item, dict)]
        if len({track.external_id for track in tracks}) != len(tracks):
            raise MusicProviderError("SunoAPI 返回了重复的音乐编号", code="SUNOAPI_INVALID_RESPONSE")
        if not tracks or any(not track.audio_url for track in tracks):
            raise MusicProviderError(
                "SunoAPI 任务已完成，但音频下载地址尚不可用",
                code="SUNO_NO_AUDIO_RESULT",
                call=call,
                retryable=True,
                detail={"external_task_id": task_id},
            )
        return MusicGenerationOutput(
            external_task_id=task_id,
            provider_status="complete",
            tracks=tracks,
            call=call,
        )

    def get_quota(self) -> MusicProviderQuota:
        started_at = utc_now()
        path = "/api/v1/generate/credit"
        response = self._request("GET", path, started_at=started_at)
        body = self._require_success_body(
            response,
            method="GET",
            path=path,
            started_at=started_at,
        )
        credits = _optional_number(body.get("data"))
        if credits is None or not math.isfinite(credits) or credits < 0:
            raise MusicProviderError(
                "SunoAPI 额度接口没有返回有效积分",
                code="SUNOAPI_INVALID_RESPONSE",
            )
        completed_at = utc_now()
        return MusicProviderQuota(
            credits_remaining=credits,
            usage=None,
            limit=None,
            period=None,
            raw={"credits_remaining": credits},
            call=self._call_metadata(
                response,
                method="GET",
                path=path,
                started_at=started_at,
                completed_at=completed_at,
                usage_unit="quota_checks",
                usage_quantity=1,
            ),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        started_at: datetime,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            if method == "POST" and not isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout)):
                raise self._submission_unknown(self._failed_call(method, path, started_at)) from exc
            raise MusicProviderError(
                "连接 SunoAPI 超时，系统将稍后重试",
                code="SUNOAPI_TIMEOUT",
                retryable=True,
                call=self._failed_call(method, path, started_at),
            ) from exc
        except httpx.HTTPError as exc:
            if method == "POST" and not isinstance(exc, httpx.ConnectError):
                raise self._submission_unknown(self._failed_call(method, path, started_at)) from exc
            raise MusicProviderError(
                "无法连接 SunoAPI，系统将稍后重试",
                code="SUNOAPI_NETWORK_ERROR",
                retryable=True,
                call=self._failed_call(method, path, started_at),
            ) from exc
        if response.is_success:
            return response
        raise self._api_error(
            response,
            method=method,
            path=path,
            started_at=started_at,
        )

    def _require_success_body(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
        started_at: datetime,
    ) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            if method == "POST":
                raise self._submission_unknown(self._failed_call(method, path, started_at)) from exc
            raise MusicProviderError(
                "SunoAPI 返回的不是有效 JSON",
                code="SUNOAPI_INVALID_RESPONSE",
                call=self._call_metadata(
                    response,
                    method=method,
                    path=path,
                    started_at=started_at,
                    completed_at=utc_now(),
                ),
            ) from exc
        if not isinstance(body, dict):
            if method == "POST":
                raise self._submission_unknown(self._failed_call(method, path, started_at))
            raise MusicProviderError(
                "SunoAPI 返回的数据结构不正确",
                code="SUNOAPI_INVALID_RESPONSE",
            )
        try:
            provider_code = int(body.get("code", 500))
        except (TypeError, ValueError):
            provider_code = 500
        if provider_code != 200:
            raise self._api_error(
                response,
                method=method,
                path=path,
                started_at=started_at,
                provider_code=provider_code,
                provider_message=str(body.get("msg") or "unknown error"),
            )
        return body

    def _api_error(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
        started_at: datetime,
        provider_code: int | None = None,
        provider_message: str | None = None,
    ) -> MusicProviderError:
        if provider_code is None:
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("code"), int):
                    provider_code = body["code"]
            except ValueError:
                pass
        code = provider_code or response.status_code
        message = provider_message or _response_error_message(response)
        call = self._call_metadata(
            response,
            method=method,
            path=path,
            started_at=started_at,
            completed_at=utc_now(),
        )
        detail = {
            "status_code": response.status_code,
            "provider_code": code,
        }
        if code == 401 or response.status_code in {401, 403}:
            return MusicProviderError(
                "SunoAPI Token 无效或已失效，请管理员更新 Token",
                code="SUNOAPI_AUTH_FAILED",
                call=call,
                detail=detail,
            )
        if provider_code == 429:
            return MusicProviderError(
                "SunoAPI 积分不足，请充值后刷新额度",
                code="SUNOAPI_QUOTA_EXHAUSTED",
                call=call,
                detail=detail,
            )
        if code in {405, 430} or response.status_code == 429:
            return MusicProviderError(
                "SunoAPI 调用频率过高，任务将稍后重试",
                code="SUNOAPI_RATE_LIMITED",
                call=call,
                retryable=True,
                retry_after_seconds=_retry_after_seconds(response),
                detail=detail,
            )
        if code == 413:
            return MusicProviderError(
                "SunoAPI 拒绝了过长的主题、歌词或风格描述",
                code="SUNOAPI_PARAMETER_TOO_LONG",
                call=call,
                detail=detail,
            )
        if code == 455 or code >= 500 or response.status_code >= 500:
            if method == "POST" and code != 455:
                return self._submission_unknown(call)
            return MusicProviderError(
                f"SunoAPI 暂时不可用：{message[:300]}",
                code="SUNOAPI_UPSTREAM_ERROR",
                call=call,
                retryable=True,
                detail=detail,
            )
        return MusicProviderError(
            f"SunoAPI 拒绝了请求：{message[:300]}",
            code="SUNOAPI_REQUEST_REJECTED",
            call=call,
            detail=detail,
        )

    def _track_output(self, item: dict[str, Any]) -> MusicTrackOutput:
        external_id = str(item.get("id") or "").strip()
        audio_url = str(item.get("audioUrl") or item.get("audio_url") or "").strip()
        if not external_id or len(external_id) > 200:
            raise MusicProviderError(
                "SunoAPI 音乐结果缺少编号",
                code="SUNOAPI_INVALID_RESPONSE",
            )
        return MusicTrackOutput(
            external_id=external_id,
            title=str(item.get("title") or "Suno 音乐")[:200],
            audio_url=audio_url,
            duration_seconds=_optional_int(item.get("duration")),
            image_url=_optional_string(
                item.get("imageUrl") or item.get("image_url")
            ),
            provider_page_url=None,
        )

    def _call_metadata(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
        started_at: datetime,
        completed_at: datetime,
        usage_unit: str = "requests",
        usage_quantity: float = 1,
        raw_usage: dict[str, Any] | None = None,
    ) -> ProviderCallMetadata:
        return ProviderCallMetadata(
            method=method,
            endpoint=f"{self.base_url}{path}",
            is_external=True,
            request_id=(
                response.headers.get("x-request-id")
                or response.headers.get("request-id")
            ),
            usage_unit=usage_unit,
            usage_quantity=usage_quantity,
            attempt_count=1,
            duration_ms=max(
                0,
                math.floor((completed_at - started_at).total_seconds() * 1000),
            ),
            raw_usage=raw_usage,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _failed_call(
        self,
        method: str,
        path: str,
        started_at: datetime,
    ) -> ProviderCallMetadata:
        completed_at = utc_now()
        return ProviderCallMetadata(
            method=method,
            endpoint=f"{self.base_url}{path}",
            is_external=True,
            attempt_count=1,
            duration_ms=max(
                0,
                math.floor((completed_at - started_at).total_seconds() * 1000),
            ),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _provider_model(self) -> str:
        raw_model = self.model.strip().lower()
        if raw_model in {"v4.5+", "v4_5+"}:
            return "V4_5PLUS"
        normalized = re.sub(r"[^a-z0-9]+", "", raw_model)
        aliases = {
            "v4": "V4",
            "v45": "V4_5",
            "v45plus": "V4_5PLUS",
            "v45all": "V4_5ALL",
            "v5": "V5",
            "v55": "V5_5",
        }
        provider_model = aliases.get(normalized)
        if provider_model is None:
            raise MusicProviderError(
                f"SunoAPI 不支持模型 {self.model}",
                code="SUNOAPI_MODEL_INVALID",
                detail={"allowed": list(aliases.values())},
            )
        return provider_model

    def _style_tags(self, payload: MusicGenerationInput) -> str:
        values = [", ".join(payload.style_tags), payload.style_prompt.strip()]
        if payload.requirements:
            values.append(payload.requirements.strip())
        return ", ".join(value for value in values if value)

    def _validate_generation_payload(
        self,
        payload: MusicGenerationInput,
        *,
        model: str,
        style: str,
    ) -> None:
        prompt_limit = 3000 if model == "V4" else 5000
        style_limit = 200 if model == "V4" else 1000
        title_limit = 80 if model in {"V4", "V4_5ALL"} else 100
        violations: dict[str, int] = {}
        if not payload.instrumental and not payload.lyrics.strip():
            raise MusicProviderError(
                "人声音乐生成必须包含歌词",
                code="SUNOAPI_LYRICS_REQUIRED",
            )
        if not style:
            raise MusicProviderError(
                "SunoAPI 自定义生成必须包含风格描述",
                code="SUNOAPI_STYLE_REQUIRED",
            )
        if len(payload.lyrics) > prompt_limit:
            violations["lyrics_limit"] = prompt_limit
        if len(style) > style_limit:
            violations["style_limit"] = style_limit
        if len(payload.title) > title_limit:
            violations["title_limit"] = title_limit
        if violations:
            raise MusicProviderError(
                "音乐参数超过当前 SunoAPI 模型的长度限制",
                code="SUNOAPI_PARAMETER_TOO_LONG",
                detail=violations,
            )

    def _validate_connection_settings(self) -> None:
        if not self.api_key:
            raise MusicProviderError(
                "尚未配置 SunoAPI Token，请管理员在音乐创作页填写",
                code="SUNOAPI_NOT_CONFIGURED",
            )
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise MusicProviderError(
                "SunoAPI 服务地址必须是完整的 HTTPS 地址",
                code="SUNOAPI_INVALID_URL",
            )

    def _validate_callback_url(self) -> None:
        parsed = urlparse(self.callback_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise MusicProviderError(
                "SunoAPI 回调公网地址必须是完整的 HTTPS 地址",
                code="SUNOAPI_CALLBACK_URL_INVALID",
            )


class SunoCompatibilityMusicProvider:
    """Adapter for an isolated gcui-art/suno-api deployment.

    Blue Music never forwards a Suno cookie. The compatibility service owns its
    session, is expected to be private, and must return a human-verification
    error instead of solving CAPTCHA challenges automatically.
    """

    name = "suno"
    implementation: MusicProviderImplementation = "compatibility"
    _complete_statuses = {"complete", "completed", "streaming", "ready"}
    _failed_statuses = {"error", "failed", "blocked"}

    def __init__(
        self,
        *,
        base_url: str | None = None,
        shared_token: str | None = None,
        model: str | None = None,
        on_submitted: Callable[[str], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not settings.SUNO_COMPAT_ENABLED:
            raise MusicProviderError(
                "Suno 兼容实现默认关闭，启用前需要完成风险确认和内网隔离",
                code="SUNO_COMPAT_DISABLED",
                detail={"implementation": self.implementation},
            )
        self.base_url = (
            base_url if base_url is not None else settings.SUNO_COMPAT_BASE_URL
        ).rstrip("/")
        self.shared_token = (
            shared_token
            if shared_token is not None
            else settings.SUNO_COMPAT_SHARED_TOKEN
        )
        self.model = model or settings.SUNO_COMPAT_MODEL or settings.SUNO_MODEL or None
        self._on_submitted = on_submitted
        self._validate_connection_settings()
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.shared_token}",
                "User-Agent": f"blue-music-platform/{settings.VERSION}",
            },
            timeout=settings.SUNO_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )

    def generate(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        request_payload: dict[str, Any] = {
            "prompt": "" if payload.instrumental else payload.lyrics,
            "tags": self._style_tags(payload),
            "title": payload.title,
            "make_instrumental": payload.instrumental,
            "wait_audio": False,
            "negative_tags": ", ".join(payload.negative_tags),
        }
        if self.model:
            request_payload["model"] = self.model
        return self._submit_and_wait(
            "/api/custom_generate",
            request_payload,
            operation="generate",
        )

    def extend(self, payload: MusicGenerationInput) -> MusicGenerationOutput:
        if not payload.source_external_id:
            raise MusicProviderError(
                "续写任务缺少 Suno 原始音频编号",
                code="SUNO_SOURCE_ID_REQUIRED",
            )
        request_payload: dict[str, Any] = {
            "audio_id": payload.source_external_id,
            "prompt": "" if payload.instrumental else payload.lyrics,
            "tags": self._style_tags(payload),
            "title": payload.title,
            "wait_audio": False,
            "negative_tags": ", ".join(payload.negative_tags),
        }
        if self.model:
            request_payload["model"] = self.model
        return self._submit_and_wait(
            "/api/extend_audio",
            request_payload,
            operation="extend",
        )

    def resume(
        self,
        payload: MusicGenerationInput,
        external_task_id: str,
    ) -> MusicGenerationOutput:
        track_ids = self._external_ids(external_task_id)
        if not track_ids:
            raise MusicProviderError(
                "Suno 外部任务编号无效，无法继续查询",
                code="SUNO_EXTERNAL_TASK_INVALID",
            )
        started_at = utc_now()
        return self._wait_for_tracks(
            track_ids,
            started_at=started_at,
            operation="resume",
        )

    def get_quota(self) -> MusicProviderQuota:
        started_at = utc_now()
        response = self._request("GET", "/api/get_limit", started_at=started_at)
        data = self._require_mapping(response)
        completed_at = utc_now()
        return MusicProviderQuota(
            credits_remaining=_optional_number(data.get("credits_left")),
            usage=_optional_number(data.get("monthly_usage")),
            limit=_optional_number(data.get("monthly_limit")),
            period=_optional_string(data.get("period")),
            raw={
                "credits_left": data.get("credits_left"),
                "monthly_usage": data.get("monthly_usage"),
                "monthly_limit": data.get("monthly_limit"),
                "period": data.get("period"),
            },
            call=self._call_metadata(
                response,
                method="GET",
                path="/api/get_limit",
                started_at=started_at,
                completed_at=completed_at,
                usage_unit="quota_checks",
                usage_quantity=1,
            ),
        )

    def get_runtime_status(self) -> dict[str, Any]:
        started_at = utc_now()
        response = self._request(
            "GET",
            "/api/health",
            started_at=started_at,
            timeout=3.0,
        )
        return self._require_mapping(response)

    def _submit_and_wait(
        self,
        path: str,
        request_payload: dict[str, Any],
        *,
        operation: str,
    ) -> MusicGenerationOutput:
        started_at = utc_now()
        response = self._request(
            "POST",
            path,
            json=request_payload,
            started_at=started_at,
        )
        items = self._require_track_list(response)
        track_ids = [
            str(item["id"]).strip()
            for item in items
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]
        if not track_ids:
            raise MusicProviderError(
                "Suno 兼容服务没有返回音频编号",
                code="SUNO_INVALID_RESPONSE",
                call=self._call_metadata(
                    response,
                    method="POST",
                    path=path,
                    started_at=started_at,
                    completed_at=utc_now(),
                ),
            )
        external_task_id = ",".join(track_ids)
        if len(external_task_id) > 200:
            raise MusicProviderError(
                "Suno 返回的外部任务编号过长，无法可靠保存",
                code="SUNO_EXTERNAL_TASK_INVALID",
            )
        if self._on_submitted is not None:
            self._on_submitted(external_task_id)
        try:
            return self._wait_for_tracks(
                track_ids,
                started_at=started_at,
                operation=operation,
                initial_items=items,
                submit_response=response,
                submit_path=path,
            )
        except MusicProviderError as exc:
            detail = dict(exc.detail or {})
            detail.setdefault("external_task_id", ",".join(track_ids))
            exc.detail = detail
            raise

    def _wait_for_tracks(
        self,
        track_ids: list[str],
        *,
        started_at: datetime,
        operation: str,
        initial_items: list[dict[str, Any]] | None = None,
        submit_response: httpx.Response | None = None,
        submit_path: str | None = None,
    ) -> MusicGenerationOutput:
        deadline = time.monotonic() + settings.SUNO_GENERATION_TIMEOUT_SECONDS
        items = initial_items or []
        poll_count = 0
        last_response = submit_response
        while True:
            returned_ids = {
                str(item.get("id") or "").strip()
                for item in items
                if isinstance(item, dict) and item.get("id")
            }
            statuses = {
                str(item.get("status") or "").strip().lower()
                for item in items
                if isinstance(item, dict)
            }
            failed_items = [
                item
                for item in items
                if str(item.get("status") or "").strip().lower()
                in self._failed_statuses
            ]
            if failed_items:
                messages = [
                    str(item.get("error_message") or "").strip()
                    for item in failed_items
                    if item.get("error_message")
                ]
                message = messages[0] if messages else "Suno 音乐生成失败"
                if _requires_human_verification(message):
                    raise MusicProviderError(
                        "Suno 要求人机验证；请管理员在 Suno 正常网页完成验证并更新兼容服务会话",
                        code="SUNO_HUMAN_VERIFICATION_REQUIRED",
                        requires_human=True,
                        detail={"provider_statuses": sorted(statuses)},
                    )
                raise MusicProviderError(
                    message,
                    code="SUNO_GENERATION_FAILED",
                    retryable=False,
                    detail={"provider_statuses": sorted(statuses)},
                )
            all_tracks_returned = set(track_ids) <= returned_ids
            if (
                items
                and all_tracks_returned
                and statuses
                and statuses <= self._complete_statuses
            ):
                break
            if time.monotonic() >= deadline:
                raise MusicProviderError(
                    "等待 Suno 生成结果超时，稍后将继续查询同一个外部任务",
                    code="SUNO_GENERATION_TIMEOUT",
                    retryable=True,
                    detail={
                        "external_task_id": ",".join(track_ids),
                        "provider_statuses": sorted(statuses),
                    },
                )
            time.sleep(max(1.0, settings.SUNO_POLL_INTERVAL_SECONDS))
            poll_count += 1
            last_response = self._request(
                "GET",
                "/api/get",
                params={"ids": ",".join(track_ids)},
                started_at=started_at,
            )
            items = self._require_track_list(last_response)

        tracks = [self._track_output(item) for item in items]
        if not tracks or any(not track.audio_url for track in tracks):
            raise MusicProviderError(
                "Suno 任务已结束，但没有返回可用音频地址",
                code="SUNO_NO_AUDIO_RESULT",
                retryable=True,
                detail={"external_task_id": ",".join(track_ids)},
            )
        completed_at = utc_now()
        response = submit_response or last_response
        if response is None:
            raise MusicProviderError(
                "Suno 兼容服务没有返回可记录的响应",
                code="SUNO_INVALID_RESPONSE",
            )
        return MusicGenerationOutput(
            external_task_id=",".join(track_ids),
            provider_status="complete",
            tracks=tracks,
            call=self._call_metadata(
                response,
                method="POST" if submit_response is not None else "GET",
                path=submit_path or "/api/get",
                started_at=started_at,
                completed_at=completed_at,
                usage_unit="songs",
                usage_quantity=len(tracks) if operation != "resume" else 0,
                raw_usage={
                    "implementation": self.implementation,
                    "operation": operation,
                    "poll_count": poll_count,
                    "track_count": len(tracks),
                },
            ),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        started_at: datetime,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise MusicProviderError(
                "连接 Suno 兼容服务超时",
                code="SUNO_COMPAT_TIMEOUT",
                retryable=True,
                call=self._failed_call(method, path, started_at),
            ) from exc
        except httpx.HTTPError as exc:
            raise MusicProviderError(
                "无法连接 Suno 兼容服务",
                code="SUNO_COMPAT_NETWORK_ERROR",
                retryable=True,
                call=self._failed_call(method, path, started_at),
            ) from exc

        if response.is_success:
            return response
        raise self._http_error(response, method, path, started_at)

    def _http_error(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        started_at: datetime,
    ) -> MusicProviderError:
        message = _response_error_message(response)
        error_code = _response_error_code(response)
        lowered = message.lower()
        call = self._call_metadata(
            response,
            method=method,
            path=path,
            started_at=started_at,
            completed_at=utc_now(),
        )
        if _requires_human_verification(lowered):
            return MusicProviderError(
                "Suno 要求人机验证；请管理员在 Suno 正常网页完成验证并更新兼容服务会话",
                code="SUNO_HUMAN_VERIFICATION_REQUIRED",
                call=call,
                requires_human=True,
                detail={"status_code": response.status_code},
            )
        if error_code == "SUNO_COOKIE_NOT_CONFIGURED":
            return MusicProviderError(
                "Suno 兼容服务尚未配置登录会话，请管理员在本机更新 Suno Cookie",
                code="SUNO_COOKIE_NOT_CONFIGURED",
                call=call,
                detail={"status_code": response.status_code},
            )
        if error_code == "UNAUTHORIZED":
            return MusicProviderError(
                "蓝乐与 Suno 兼容服务的内部令牌不一致",
                code="SUNO_COMPAT_AUTH_FAILED",
                call=call,
                detail={"status_code": response.status_code},
            )
        if response.status_code in (401, 403):
            return MusicProviderError(
                "Suno 兼容服务会话已失效或访问被拒绝，请管理员更新会话",
                code="SUNO_SESSION_EXPIRED",
                call=call,
                detail={"status_code": response.status_code},
            )
        if response.status_code == 402:
            return MusicProviderError(
                "Suno 账户额度不足，请检查订阅或剩余额度",
                code="SUNO_QUOTA_EXHAUSTED",
                call=call,
                detail={"status_code": response.status_code},
            )
        if response.status_code == 429:
            retry_after = _retry_after_seconds(response)
            return MusicProviderError(
                "Suno 当前请求过多，任务将按限频策略稍后重试",
                code="SUNO_RATE_LIMITED",
                call=call,
                retryable=True,
                retry_after_seconds=retry_after,
                detail={"status_code": response.status_code},
            )
        if response.status_code >= 500:
            return MusicProviderError(
                f"Suno 兼容服务暂时异常（HTTP {response.status_code}）",
                code="SUNO_COMPAT_UPSTREAM_ERROR",
                call=call,
                retryable=True,
                detail={"status_code": response.status_code},
            )
        return MusicProviderError(
            f"Suno 兼容服务拒绝了请求（HTTP {response.status_code}）：{message}",
            code="SUNO_COMPAT_REQUEST_REJECTED",
            call=call,
            detail={"status_code": response.status_code},
        )

    def _require_mapping(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise MusicProviderError(
                "Suno 兼容服务返回的不是有效 JSON",
                code="SUNO_INVALID_RESPONSE",
            ) from exc
        if not isinstance(data, dict):
            raise MusicProviderError(
                "Suno 兼容服务返回的数据结构不正确",
                code="SUNO_INVALID_RESPONSE",
            )
        if data.get("error"):
            message = str(data["error"])
            if _requires_human_verification(message):
                raise MusicProviderError(
                    "Suno 要求人机验证；请管理员在 Suno 正常网页完成验证并更新兼容服务会话",
                    code="SUNO_HUMAN_VERIFICATION_REQUIRED",
                    requires_human=True,
                )
            raise MusicProviderError(
                f"Suno 兼容服务返回错误：{message}",
                code="SUNO_COMPAT_UPSTREAM_ERROR",
                retryable=True,
            )
        return data

    def _require_track_list(
        self,
        response: httpx.Response,
    ) -> list[dict[str, Any]]:
        try:
            data = response.json()
        except ValueError as exc:
            raise MusicProviderError(
                "Suno 兼容服务返回的不是有效 JSON",
                code="SUNO_INVALID_RESPONSE",
            ) from exc
        if isinstance(data, dict) and data.get("error"):
            message = str(data["error"])
            if _requires_human_verification(message):
                raise MusicProviderError(
                    "Suno 要求人机验证；请管理员在 Suno 正常网页完成验证并更新兼容服务会话",
                    code="SUNO_HUMAN_VERIFICATION_REQUIRED",
                    requires_human=True,
                )
            raise MusicProviderError(
                f"Suno 兼容服务返回错误：{message}",
                code="SUNO_COMPAT_UPSTREAM_ERROR",
                retryable=True,
            )
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise MusicProviderError(
                "Suno 兼容服务没有返回音频列表",
                code="SUNO_INVALID_RESPONSE",
            )
        return data

    def _track_output(self, item: dict[str, Any]) -> MusicTrackOutput:
        external_id = str(item.get("id") or "").strip()
        audio_url = str(item.get("audio_url") or "").strip()
        if not external_id:
            raise MusicProviderError(
                "Suno 音频结果缺少编号",
                code="SUNO_INVALID_RESPONSE",
            )
        return MusicTrackOutput(
            external_id=external_id,
            title=str(item.get("title") or "Suno 音乐")[:200],
            audio_url=audio_url,
            duration_seconds=_optional_int(item.get("duration")),
            image_url=_optional_string(item.get("image_url")),
            provider_page_url=f"https://suno.com/song/{external_id}",
        )

    def _call_metadata(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
        started_at: datetime,
        completed_at: datetime,
        usage_unit: str = "requests",
        usage_quantity: float = 1,
        raw_usage: dict[str, Any] | None = None,
    ) -> ProviderCallMetadata:
        return ProviderCallMetadata(
            method=method,
            endpoint=f"{self.base_url}{path}",
            is_external=True,
            request_id=(
                response.headers.get("x-request-id")
                or response.headers.get("request-id")
            ),
            usage_unit=usage_unit,
            usage_quantity=usage_quantity,
            attempt_count=1,
            duration_ms=max(
                0,
                math.floor((completed_at - started_at).total_seconds() * 1000),
            ),
            raw_usage=raw_usage,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _failed_call(
        self,
        method: str,
        path: str,
        started_at: datetime,
    ) -> ProviderCallMetadata:
        completed_at = utc_now()
        return ProviderCallMetadata(
            method=method,
            endpoint=f"{self.base_url}{path}",
            is_external=True,
            attempt_count=1,
            duration_ms=max(
                0,
                math.floor((completed_at - started_at).total_seconds() * 1000),
            ),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _style_tags(self, payload: MusicGenerationInput) -> str:
        values = [", ".join(payload.style_tags), payload.style_prompt.strip()]
        if payload.requirements:
            values.append(payload.requirements.strip())
        return ", ".join(value for value in values if value)

    def _validate_connection_settings(self) -> None:
        if not self.base_url:
            raise MusicProviderError(
                "尚未配置 Suno 兼容服务地址",
                code="SUNO_COMPAT_NOT_CONFIGURED",
            )
        parsed = urlparse(self.base_url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise MusicProviderError(
                "Suno 兼容服务地址格式不安全",
                code="SUNO_COMPAT_INVALID_URL",
            )
        local_names = {"localhost", "127.0.0.1", "::1"}
        internal_service_name = "." not in hostname
        if not settings.SUNO_COMPAT_ALLOW_REMOTE and not (
            hostname in local_names or internal_service_name
        ):
            raise MusicProviderError(
                "Suno 兼容服务只允许连接本机或 Docker 内网地址",
                code="SUNO_COMPAT_REMOTE_FORBIDDEN",
            )
        if settings.SUNO_COMPAT_ALLOW_REMOTE and parsed.scheme != "https":
            raise MusicProviderError(
                "远程 Suno 兼容服务必须使用 HTTPS",
                code="SUNO_COMPAT_HTTPS_REQUIRED",
            )
        if not self.shared_token:
            raise MusicProviderError(
                "Suno 兼容服务缺少内部共享令牌",
                code="SUNO_COMPAT_TOKEN_REQUIRED",
            )

    @staticmethod
    def _external_ids(external_task_id: str) -> list[str]:
        return [
            value.strip()
            for value in external_task_id.split(",")
            if value.strip()
        ]


def get_music_provider(
    implementation: MusicProviderImplementation | str | None = None,
    *,
    model: str | None = None,
    on_submitted: Callable[[str], None] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    callback_url: str | None = None,
) -> MusicGenerationProvider:
    selected = (
        implementation or settings.SUNO_PROVIDER_IMPLEMENTATION
    ).strip().lower()
    if selected == "official":
        return SunoOfficialMusicProvider(model=model)
    if selected in {"sunoapi", "sunoapi_org", "sunoapi.org"}:
        return SunoApiOrgMusicProvider(
            api_key=api_key,
            base_url=base_url,
            callback_url=callback_url,
            model=model,
            on_submitted=on_submitted,
        )
    if selected in {"compat", "compatibility"}:
        return SunoCompatibilityMusicProvider(
            model=model,
            on_submitted=on_submitted,
        )
    raise MusicProviderError(
        f"不支持的 Suno Provider 实现：{selected}",
        code="SUNO_PROVIDER_IMPLEMENTATION_INVALID",
        detail={"allowed": ["official", "sunoapi_org", "compatibility"]},
    )


def _response_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text.strip()[:500] or response.reason_phrase
    if isinstance(data, dict):
        for key in ("error", "detail", "message"):
            value = data.get(key)
            if value:
                return str(value)[:500]
    return str(data)[:500]


def _response_error_code(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("code")
    return str(value).strip()[:100] if value else None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _requires_human_verification(message: str) -> bool:
    lowered = message.lower()
    return any(
        value in lowered
        for value in ("captcha", "hcaptcha", "人机验证", "human verification")
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    number = _optional_number(value)
    if number is None:
        return None
    return max(0, round(number))
