import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import DatabaseSession, SuperAdmin, require_agent_permission
from app.core.config import settings
from app.core.exceptions import AppException
from app.models import AgentType, User, UserRole
from app.schemas.music import (
    MusicCreateRequest,
    MusicExtendRequest,
    MusicResultListResponse,
    MusicTaskDeleteRequest,
    MusicTaskDeleteResponse,
    MusicTaskListResponse,
    MusicTaskResponse,
    SunoQuotaResponse,
    SunoProviderStatusResponse,
)
from app.services.music import (
    create_extension_task,
    create_music_task,
    delete_music_result,
    delete_music_task,
    delete_music_tasks,
    dispatch_music_task,
    create_storage_download_url,
    get_music_result,
    get_music_task,
    latest_music_quota,
    list_music_results,
    list_music_tasks,
    refresh_music_quota,
    resolve_storage_path,
    retry_music_task,
)


router = APIRouter(prefix="/music")
MusicUser = Annotated[User, Depends(require_agent_permission(AgentType.MUSIC))]


@router.get("/provider-status", response_model=SunoProviderStatusResponse)
def provider_status(
    db: DatabaseSession,
    user: MusicUser,
) -> SunoProviderStatusResponse:
    raw_implementation = settings.SUNO_PROVIDER_IMPLEMENTATION
    implementation = raw_implementation
    if implementation == "compat":
        implementation = "compatibility"
    if implementation == "official":
        configured = bool(settings.SUNO_API_BASE_URL and settings.SUNO_API_KEY)
        integration_status = "contract_pending" if configured else "waiting_access"
        message = (
            "Suno 官方账号已配置，等待按账号内正式文档完成接口合同映射"
            if configured
            else "等待在 Suno Platform 获得官方 API 访问权限和密钥"
        )
    elif implementation == "compatibility":
        configured = bool(
            settings.SUNO_COMPAT_ENABLED
            and settings.SUNO_COMPAT_BASE_URL
            and settings.SUNO_COMPAT_SHARED_TOKEN
        )
        if not settings.SUNO_COMPAT_ENABLED:
            integration_status = "disabled"
            message = "Suno 兼容实现已安装但默认关闭"
        elif configured:
            integration_status = "ready"
            message = "Suno 兼容实现已连接到隔离服务；人机验证需要管理员处理"
        else:
            integration_status = "configuration_error"
            message = "Suno 兼容实现缺少服务地址或内部共享令牌"
    else:
        implementation = "invalid"
        configured = False
        integration_status = "configuration_error"
        message = f"不支持的 Suno Provider 实现：{raw_implementation}"
    return SunoProviderStatusResponse(
        implementation=implementation,
        configured=configured,
        integration_status=integration_status,
        message=message,
        queue_mode=settings.MUSIC_QUEUE_MODE,
        max_concurrency=max(1, settings.MUSIC_MAX_CONCURRENCY),
        min_request_interval_seconds=max(
            0.0, settings.MUSIC_MIN_REQUEST_INTERVAL_SECONDS
        ),
        quota=(
            latest_music_quota(db, implementation)
            if user.role == UserRole.SUPER_ADMIN
            else None
        ),
    )


@router.post("/provider-status/refresh", response_model=SunoQuotaResponse)
def provider_quota_refresh(
    db: DatabaseSession,
    admin: SuperAdmin,
) -> SunoQuotaResponse:
    return refresh_music_quota(db)


@router.post(
    "/tasks",
    response_model=MusicTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def music_create(
    payload: MusicCreateRequest,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    task = create_music_task(db, payload, user.id)
    return dispatch_music_task(db, task.id)


@router.get("/tasks", response_model=MusicTaskListResponse)
def music_history(
    db: DatabaseSession,
    user: MusicUser,
    limit: int = Query(default=15, ge=1, le=100),
) -> MusicTaskListResponse:
    return list_music_tasks(db, limit)


@router.delete("/tasks", response_model=MusicTaskDeleteResponse)
def music_bulk_delete(
    payload: MusicTaskDeleteRequest,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskDeleteResponse:
    return delete_music_tasks(db, payload.task_ids)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def music_delete(
    task_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> Response:
    delete_music_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}", response_model=MusicTaskResponse)
def music_detail(
    task_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    return get_music_task(db, task_id)


@router.post("/tasks/{task_id}/retry", response_model=MusicTaskResponse)
def music_retry(
    task_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    return retry_music_task(db, task_id)


@router.post(
    "/results/{result_id}/extend",
    response_model=MusicTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def music_extend(
    result_id: int,
    payload: MusicExtendRequest,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    task = create_extension_task(db, result_id, payload, user.id)
    return dispatch_music_task(db, task.id)


@router.get("/results", response_model=MusicResultListResponse)
def music_results(
    db: DatabaseSession,
    user: MusicUser,
    limit: int = Query(default=30, ge=1, le=100),
) -> MusicResultListResponse:
    return list_music_results(db, limit)


@router.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def music_result_delete(
    result_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> Response:
    delete_music_result(db, result_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/results/{result_id}/audio", response_model=None)
def music_audio(
    result_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> FileResponse | RedirectResponse:
    result = get_music_result(db, result_id)
    local_path = resolve_storage_path(
        result.storage_key,
        result.storage_backend,
    )
    if local_path is not None:
        return FileResponse(local_path, media_type=result.media_type)
    storage_url = create_storage_download_url(
        result,
        filename=_download_filename(result.title, Path("track.mp3")),
        attachment=False,
    )
    if storage_url:
        return RedirectResponse(storage_url, status_code=307)
    if result.audio_url:
        return RedirectResponse(result.audio_url, status_code=307)
    raise AppException(
        code="MUSIC_AUDIO_UNAVAILABLE",
        message="该音乐暂时没有可播放的音频文件",
        status_code=404,
    )


@router.get("/results/{result_id}/download", response_model=None)
def music_download(
    result_id: int,
    db: DatabaseSession,
    user: MusicUser,
) -> FileResponse | RedirectResponse:
    result = get_music_result(db, result_id)
    local_path = resolve_storage_path(
        result.storage_key,
        result.storage_backend,
    )
    if local_path is not None:
        return FileResponse(
            local_path,
            media_type=result.media_type,
            filename=_download_filename(result.title, local_path),
        )
    storage_url = create_storage_download_url(
        result,
        filename=_download_filename(result.title, Path("track.mp3")),
        attachment=True,
    )
    if storage_url:
        return RedirectResponse(storage_url, status_code=307)
    raise AppException(
        code="MUSIC_AUDIO_NOT_ARCHIVED",
        message="音频尚未归档到平台，暂时不能下载",
        status_code=503,
        detail={"storage_error": result.storage_error},
    )


def _download_filename(title: str, path: Path) -> str:
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" ._")
    return f"{safe_title or 'suno-track'}{path.suffix.lower()}"
