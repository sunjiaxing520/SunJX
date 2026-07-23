import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import DatabaseSession, require_agent_permission
from app.core.config import settings
from app.core.exceptions import AppException
from app.models import AgentType, User
from app.schemas.music import (
    MusicCreateRequest,
    MusicExtendRequest,
    MusicResultListResponse,
    MusicTaskDeleteRequest,
    MusicTaskDeleteResponse,
    MusicTaskListResponse,
    MusicTaskResponse,
    SunoProviderStatusResponse,
)
from app.services.music import (
    create_extension_task,
    create_music_task,
    delete_music_result,
    delete_music_task,
    delete_music_tasks,
    execute_music_task,
    get_music_result,
    get_music_task,
    list_music_results,
    list_music_tasks,
    resolve_storage_path,
)


router = APIRouter(prefix="/music")
MusicUser = Annotated[User, Depends(require_agent_permission(AgentType.MUSIC))]


@router.get("/provider-status", response_model=SunoProviderStatusResponse)
def provider_status(user: MusicUser) -> SunoProviderStatusResponse:
    configured = bool(settings.SUNO_API_BASE_URL and settings.SUNO_API_KEY)
    return SunoProviderStatusResponse(
        configured=configured,
        integration_status="contract_pending" if configured else "waiting_access",
        message=(
            "Suno 官方账号已配置，等待按正式文档完成接口联调"
            if configured
            else "等待在 Suno Platform 获得官方 API 访问权限和密钥"
        ),
    )


@router.post(
    "/tasks",
    response_model=MusicTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def music_create(
    payload: MusicCreateRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    task = create_music_task(db, payload, user.id)
    background_tasks.add_task(execute_music_task, task.id, db.get_bind())
    return task


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


@router.post(
    "/results/{result_id}/extend",
    response_model=MusicTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def music_extend(
    result_id: int,
    payload: MusicExtendRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: MusicUser,
) -> MusicTaskResponse:
    task = create_extension_task(db, result_id, payload, user.id)
    background_tasks.add_task(execute_music_task, task.id, db.get_bind())
    return task


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
    local_path = resolve_storage_path(result.storage_key)
    if local_path is not None:
        return FileResponse(local_path, media_type=result.media_type)
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
) -> FileResponse:
    result = get_music_result(db, result_id)
    local_path = resolve_storage_path(result.storage_key)
    if local_path is None:
        raise AppException(
            code="MUSIC_AUDIO_NOT_ARCHIVED",
            message="音频尚未归档到平台，暂时不能下载",
            status_code=503,
            detail={"storage_error": result.storage_error},
        )
    return FileResponse(
        local_path,
        media_type=result.media_type,
        filename=_download_filename(result.title, local_path),
    )


def _download_filename(title: str, path: Path) -> str:
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" ._")
    return f"{safe_title or 'suno-track'}{path.suffix.lower()}"
