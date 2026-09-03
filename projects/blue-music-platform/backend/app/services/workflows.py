import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Engine, Connection, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import LOGGER_NAME
from app.core.time import utc_now
from app.models import (
    AgentType,
    AnalysisReport,
    LyricsVersion,
    RankingEntry,
    TaskStatus,
    User,
    UserAgentPermission,
    UserRole,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStepType,
    WorkflowTemplate,
)
from app.schemas.analysis import AnalysisCreateRequest
from app.schemas.lyrics import LyricsAssistantMessageRequest, LyricsCreateRequest
from app.schemas.music import MusicCreateRequest, MusicReferenceRunCreateRequest
from app.schemas.ranking import CollectionCreateRequest
from app.schemas.review_agent import ReviewCreateRequest
from app.schemas.workflow import (
    WorkflowConfiguration,
    WorkflowRunDeleteResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowRunStepResponse,
    WorkflowReviewDecisionRequest,
    WorkflowTemplateResponse,
    WorkflowTemplateWrite,
)
from app.services.analysis import create_analysis
from app.services.lyrics import (
    confirm_lyrics_assistant_preview,
    create_lyrics_assistant_preview,
    create_lyrics_task,
    regenerate_lyrics,
)
from app.services.lyrics_prompt import (
    screen_lyrics_prompt,
    screen_optional_lyrics_prompt,
)
from app.services.music import (
    create_music_task,
    dispatch_music_task,
    wait_for_music_task_completion,
)
from app.services.rankings import create_collection
from app.services.review_agents import create_lyrics_review, require_review_agent_access


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")
STEP_AGENT = {
    WorkflowStepType.COLLECTION.value: AgentType.CRAWLER,
    WorkflowStepType.ANALYSIS.value: AgentType.ANALYSIS,
    WorkflowStepType.LYRICS.value: AgentType.LYRICS,
    WorkflowStepType.MUSIC.value: AgentType.MUSIC,
}
REFERENCE_WORKFLOW_STEPS = [
    WorkflowStepType.ANALYSIS.value,
    WorkflowStepType.LYRICS.value,
    WorkflowStepType.MUSIC.value,
]
REFERENCE_DEFAULT_REQUIREMENTS = (
    "生成一首完整的新歌曲。只借鉴参考分析中的抽象曲风、情绪、节奏、结构和配器方向，"
    "不得复制来源歌曲的具体歌词、旋律、标志性段落或歌手声线。"
)


@dataclass(frozen=True)
class _StepOutcome:
    task_id: int
    output_id: int | None
    detail: dict[str, object] | None = None


class _WorkflowReviewPause(Exception):
    def __init__(self, outcome: _StepOutcome, message: str) -> None:
        super().__init__(message)
        self.outcome = outcome
        self.message = message


def _username(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return db.scalar(select(User.username).where(User.id == user_id))


def workflow_template_response(
    db: Session, template: WorkflowTemplate
) -> WorkflowTemplateResponse:
    return WorkflowTemplateResponse(
        id=template.id,
        name=template.name,
        steps=template.steps,
        configuration=template.configuration,
        created_by_id=template.created_by_id,
        created_by_username=_username(db, template.created_by_id),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def workflow_run_response(db: Session, run: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=run.id,
        template_id=run.template_id,
        template_name=run.template_name,
        configuration=run.configuration,
        status=run.status,
        current_step=run.current_step,
        requested_by_id=run.requested_by_id,
        requested_by_username=_username(db, run.requested_by_id),
        error_code=run.error_code,
        error_message=run.error_message,
        error_detail=run.error_detail,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        steps=[
            WorkflowRunStepResponse(
                id=step.id,
                step_type=step.step_type,
                position=step.position,
                status=step.status,
                task_id=step.task_id,
                output_id=step.output_id,
                result_detail=step.result_detail,
                error_code=step.error_code,
                error_message=step.error_message,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            for step in sorted(run.steps, key=lambda value: value.position)
        ],
    )


def _ensure_step_permissions(
    db: Session,
    user: User,
    steps: list[str],
) -> None:
    if user.role == UserRole.SUPER_ADMIN:
        return
    if WorkflowStepType.COLLECTION.value in steps:
        raise AppException(
            code="WORKFLOW_PERMISSION_DENIED",
            message="榜单采集步骤仅限超级管理员使用",
            status_code=403,
            detail={"missing_steps": [WorkflowStepType.COLLECTION.value]},
        )
    permissions = set(
        db.scalars(
            select(UserAgentPermission.agent).where(
                UserAgentPermission.user_id == user.id
            )
        ).all()
    )
    missing = [
        step
        for step in steps
        if step in STEP_AGENT and STEP_AGENT[step] not in permissions
    ]
    if missing:
        raise AppException(
            code="WORKFLOW_PERMISSION_DENIED",
            message="当前账号没有所选流程步骤的使用权限",
            status_code=403,
            detail={"missing_steps": missing},
        )


def _ensure_review_step_access(
    db: Session,
    user: User,
    steps: list[str],
    configuration: WorkflowConfiguration,
) -> None:
    if WorkflowStepType.REVIEW.value not in steps:
        return
    agent_id = configuration.review.agent_id
    if agent_id is None:
        raise AppException(
            code="WORKFLOW_REVIEW_AGENT_REQUIRED",
            message="歌词审核步骤必须指定审核智能体",
            status_code=422,
        )
    require_review_agent_access(db, agent_id, user)


def _get_template(db: Session, template_id: int) -> WorkflowTemplate:
    template = db.get(WorkflowTemplate, template_id)
    if template is None:
        raise AppException(
            code="WORKFLOW_TEMPLATE_NOT_FOUND",
            message="流程模板不存在",
            status_code=404,
        )
    return template


def _ensure_unique_name(
    db: Session,
    name: str,
    *,
    exclude_id: int | None = None,
) -> None:
    statement = select(WorkflowTemplate.id).where(WorkflowTemplate.name == name)
    if exclude_id is not None:
        statement = statement.where(WorkflowTemplate.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise AppException(
            code="WORKFLOW_NAME_CONFLICT",
            message="已经存在同名流程，请换一个名称",
            status_code=409,
        )


def _screen_workflow_lyrics_prompt(payload: WorkflowTemplateWrite) -> None:
    if WorkflowStepType.LYRICS.value not in payload.steps:
        return
    lyrics = payload.configuration.lyrics
    if lyrics.theme:
        lyrics.theme = screen_lyrics_prompt(
            lyrics.theme,
            field_name="自动流程歌曲主题",
            allow_short_topic=True,
        )
    lyrics.requirements = screen_optional_lyrics_prompt(
        lyrics.requirements,
        field_name="自动流程作词要求",
    )


def list_workflow_templates(db: Session) -> list[WorkflowTemplateResponse]:
    templates = db.scalars(
        select(WorkflowTemplate).order_by(
            WorkflowTemplate.updated_at.desc(), WorkflowTemplate.id.desc()
        )
    ).all()
    return [workflow_template_response(db, template) for template in templates]


def create_workflow_template(
    db: Session,
    payload: WorkflowTemplateWrite,
    user: User,
) -> WorkflowTemplateResponse:
    _ensure_step_permissions(db, user, list(payload.steps))
    _ensure_review_step_access(db, user, list(payload.steps), payload.configuration)
    _screen_workflow_lyrics_prompt(payload)
    _ensure_unique_name(db, payload.name)
    template = WorkflowTemplate(
        name=payload.name,
        steps=list(payload.steps),
        configuration=payload.configuration.model_dump(mode="json"),
        created_by_id=user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return workflow_template_response(db, template)


def update_workflow_template(
    db: Session,
    template_id: int,
    payload: WorkflowTemplateWrite,
    user: User,
) -> WorkflowTemplateResponse:
    template = _get_template(db, template_id)
    _ensure_step_permissions(db, user, list(payload.steps))
    _ensure_review_step_access(db, user, list(payload.steps), payload.configuration)
    _screen_workflow_lyrics_prompt(payload)
    _ensure_unique_name(db, payload.name, exclude_id=template.id)
    template.name = payload.name
    template.steps = list(payload.steps)
    template.configuration = payload.configuration.model_dump(mode="json")
    db.commit()
    db.refresh(template)
    return workflow_template_response(db, template)


def delete_workflow_template(db: Session, template_id: int) -> None:
    template = _get_template(db, template_id)
    db.delete(template)
    db.commit()


def start_workflow_run(
    db: Session,
    template_id: int,
    user: User,
) -> WorkflowRunResponse:
    recover_stale_workflow_runs(db)
    _ensure_no_active_workflow_run(db)

    template = _get_template(db, template_id)
    _ensure_step_permissions(db, user, template.steps)
    configuration = WorkflowConfiguration.model_validate(template.configuration)
    _ensure_review_step_access(db, user, template.steps, configuration)
    run = WorkflowRun(
        template_id=template.id,
        template_name=template.name,
        configuration=template.configuration,
        status=TaskStatus.PENDING.value,
        requested_by_id=user.id,
        steps=[
            WorkflowRunStep(
                step_type=step_type,
                position=position,
                status=TaskStatus.PENDING.value,
            )
            for position, step_type in enumerate(template.steps)
        ],
    )
    db.add(run)
    db.commit()
    return get_workflow_run(db, run.id)


def start_reference_workflow_run(
    db: Session,
    payload: MusicReferenceRunCreateRequest,
    user: User,
) -> WorkflowRunResponse:
    recover_stale_workflow_runs(db)
    _ensure_no_active_workflow_run(db)
    entry = db.get(RankingEntry, payload.source_entry_id)
    if entry is None:
        raise AppException(
            code="MUSIC_REFERENCE_SONG_NOT_FOUND",
            message="参考歌曲不存在或采集记录已经过期",
            status_code=404,
        )
    _ensure_step_permissions(db, user, REFERENCE_WORKFLOW_STEPS)
    instruction = screen_optional_lyrics_prompt(
        payload.instruction,
        field_name="参考创作要求",
    )
    requirements = _reference_requirements(instruction)
    configuration = WorkflowConfiguration.model_validate(
        {
            "analysis": {"window_days": 7},
            "lyrics": {"requirements": requirements},
            "music": {"requirements": requirements},
            "reference": {
                "source_entry_id": entry.id,
                "instruction": instruction,
            },
        }
    )
    run = WorkflowRun(
        template_id=None,
        template_name=f"参考创作 · {entry.title}"[:100],
        configuration=configuration.model_dump(mode="json"),
        status=TaskStatus.PENDING.value,
        requested_by_id=user.id,
        steps=[
            WorkflowRunStep(
                step_type=step_type,
                position=position,
                status=TaskStatus.PENDING.value,
            )
            for position, step_type in enumerate(REFERENCE_WORKFLOW_STEPS)
        ],
    )
    db.add(run)
    db.commit()
    return get_workflow_run(db, run.id)


def _ensure_no_active_workflow_run(db: Session) -> None:
    active_run = db.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.status.in_(
                (
                    TaskStatus.PENDING.value,
                    TaskStatus.RUNNING.value,
                    TaskStatus.PAUSED.value,
                )
            )
        )
        .order_by(WorkflowRun.created_at)
        .limit(1)
    )
    if active_run is not None:
        raise AppException(
            code="WORKFLOW_ALREADY_RUNNING",
            message="已有自动流程正在运行，请等待完成后再启动下一条",
            status_code=409,
            detail={"run_id": active_run.id},
        )


def _load_run(db: Session, run_id: int) -> WorkflowRun | None:
    return db.scalar(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.steps))
        .where(WorkflowRun.id == run_id)
    )


def get_workflow_run(db: Session, run_id: int) -> WorkflowRunResponse:
    recover_stale_workflow_runs(db)
    run = _load_run(db, run_id)
    if run is None:
        raise AppException(
            code="WORKFLOW_RUN_NOT_FOUND",
            message="流程运行记录不存在",
            status_code=404,
        )
    return workflow_run_response(db, run)


def list_workflow_runs(
    db: Session,
    limit: int = 15,
) -> WorkflowRunListResponse:
    recover_stale_workflow_runs(db)
    runs = db.scalars(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.steps))
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(WorkflowRun.id))) or 0
    return WorkflowRunListResponse(
        items=[workflow_run_response(db, run) for run in runs],
        total=total,
    )


def delete_workflow_run(db: Session, run_id: int) -> None:
    delete_workflow_runs(db, [run_id])


def delete_workflow_runs(
    db: Session,
    run_ids: list[int],
) -> WorkflowRunDeleteResponse:
    recover_stale_workflow_runs(db)
    ordered_ids = list(dict.fromkeys(run_ids))
    runs = db.scalars(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.steps))
        .where(WorkflowRun.id.in_(ordered_ids))
        .with_for_update()
    ).all()
    runs_by_id = {run.id: run for run in runs}
    missing_ids = [run_id for run_id in ordered_ids if run_id not in runs_by_id]
    if missing_ids:
        raise AppException(
            code="WORKFLOW_RUN_NOT_FOUND",
            message="部分流程运行记录不存在或已经被删除",
            status_code=404,
            detail={"missing_run_ids": missing_ids},
        )

    active_ids = [
        run.id
        for run in runs
        if run.status
        in (
            TaskStatus.PENDING.value,
            TaskStatus.RUNNING.value,
            TaskStatus.PAUSED.value,
        )
    ]
    if active_ids:
        raise AppException(
            code="WORKFLOW_RUN_DELETE_CONFLICT",
            message="运行中或等待人工决定的自动流程不能删除，请先处理当前流程",
            status_code=409,
            detail={"active_run_ids": active_ids},
        )

    for run_id in ordered_ids:
        db.delete(runs_by_id[run_id])
    db.commit()
    return WorkflowRunDeleteResponse(
        deleted_count=len(ordered_ids),
        deleted_run_ids=ordered_ids,
    )


def resolve_workflow_review(
    db: Session,
    run_id: int,
    payload: WorkflowReviewDecisionRequest,
    user: User,
) -> WorkflowRunResponse:
    run = db.scalar(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.steps))
        .where(WorkflowRun.id == run_id)
        .with_for_update()
    )
    if run is None:
        raise AppException(
            code="WORKFLOW_RUN_NOT_FOUND",
            message="流程运行记录不存在",
            status_code=404,
        )
    if run.status != TaskStatus.PAUSED.value:
        raise AppException(
            code="WORKFLOW_REVIEW_NOT_PAUSED",
            message="当前流程不在等待歌词审核决定的状态",
            status_code=409,
        )
    configuration = WorkflowConfiguration.model_validate(run.configuration)
    _ensure_step_permissions(db, user, [step.step_type for step in run.steps])
    _ensure_review_step_access(
        db,
        user,
        [step.step_type for step in run.steps],
        configuration,
    )
    review_step = next(
        (
            step
            for step in run.steps
            if step.step_type == WorkflowStepType.REVIEW.value
            and step.status == TaskStatus.PAUSED.value
        ),
        None,
    )
    if review_step is None or review_step.output_id is None:
        raise AppException(
            code="WORKFLOW_REVIEW_OUTPUT_MISSING",
            message="暂停流程缺少可处理的歌词审核产出",
            status_code=409,
        )
    if db.get(LyricsVersion, review_step.output_id) is None:
        raise AppException(
            code="WORKFLOW_LYRICS_OUTPUT_MISSING",
            message="待处理歌词版本不存在或已经被删除",
            status_code=409,
        )

    now = utc_now()
    detail = dict(review_step.result_detail or run.error_detail or {})
    cycles = [
        dict(value)
        for value in list(detail.get("cycles") or [])
        if isinstance(value, dict)
    ]
    resolution: dict[str, object] = {
        "action": payload.action,
        "user_id": user.id,
        "resolved_at": now.isoformat(),
    }
    if payload.instruction:
        resolution["instruction"] = payload.instruction
    if cycles:
        cycles[-1] = {**cycles[-1], "resolution": resolution}
    detail["cycles"] = cycles
    detail["last_resolution"] = resolution

    review_step.error_code = None
    review_step.error_message = None
    if payload.action == "accept":
        detail["status"] = "accepted_by_user"
        review_step.status = TaskStatus.COMPLETED.value
        review_step.completed_at = now
    else:
        detail["status"] = "resuming"
        detail["resume_action"] = payload.action
        if payload.instruction:
            detail["resume_instruction"] = payload.instruction
        else:
            detail.pop("resume_instruction", None)
        review_step.status = TaskStatus.PENDING.value
        review_step.task_id = None
        review_step.started_at = None
        review_step.completed_at = None
    review_step.result_detail = detail

    run.status = TaskStatus.PENDING.value
    run.current_step = None
    run.error_code = None
    run.error_message = None
    run.error_detail = None
    run.started_at = now
    run.completed_at = None
    db.commit()
    return get_workflow_run(db, run.id)


def execute_workflow_run(
    run_id: int,
    bind: Engine | Connection,
) -> None:
    session_factory = sessionmaker(
        bind=bind,
        autocommit=False,
        autoflush=False,
    )
    with session_factory() as db:
        run = _load_run(db, run_id)
        if run is None or run.status != TaskStatus.PENDING.value:
            return
        run.status = TaskStatus.RUNNING.value
        run.started_at = run.started_at or utc_now()
        run.completed_at = None
        db.commit()
        task_logger.info(
            "workflow_run_started",
            extra={"task_id": str(run.id), "task_type": "workflow"},
        )

        configuration = WorkflowConfiguration.model_validate(run.configuration)
        analysis_report_id: int | None = None
        collected_snapshot_id: int | None = None
        lyrics_version_id: int | None = None

        for step in sorted(run.steps, key=lambda value: value.position):
            if step.status == TaskStatus.COMPLETED.value:
                if step.step_type == WorkflowStepType.COLLECTION.value:
                    collected_snapshot_id = step.output_id
                elif step.step_type == WorkflowStepType.ANALYSIS.value:
                    analysis_report_id = step.output_id
                elif step.step_type in (
                    WorkflowStepType.LYRICS.value,
                    WorkflowStepType.REVIEW.value,
                ):
                    lyrics_version_id = step.output_id
                continue
            if step.step_type == WorkflowStepType.REVIEW.value and step.output_id:
                lyrics_version_id = step.output_id
            if step.status != TaskStatus.PENDING.value:
                _mark_workflow_failed(
                    db,
                    run.id,
                    step.id,
                    AppException(
                        code="WORKFLOW_STEP_STATE_INVALID",
                        message="自动流程步骤状态异常，无法继续执行",
                        status_code=409,
                        detail={"step_type": step.step_type, "status": step.status},
                    ),
                )
                return
            _mark_step_running(db, run.id, step.id, step.step_type)
            try:
                outcome = _execute_step(
                    db,
                    run,
                    step,
                    configuration,
                    collected_snapshot_id=collected_snapshot_id,
                    analysis_report_id=analysis_report_id,
                    lyrics_version_id=lyrics_version_id,
                )
            except _WorkflowReviewPause as pause:
                _mark_workflow_paused(db, run.id, step.id, pause)
                return
            except AppException as exc:
                _mark_workflow_failed(db, run.id, step.id, exc)
                return
            except Exception as exc:
                task_logger.exception(
                    "workflow_run_failed",
                    extra={
                        "task_id": str(run.id),
                        "task_type": "workflow",
                        "error_code": "WORKFLOW_UNEXPECTED_ERROR",
                    },
                )
                _mark_workflow_failed(
                    db,
                    run.id,
                    step.id,
                    AppException(
                        code="WORKFLOW_UNEXPECTED_ERROR",
                        message="自动流程发生未预期错误，请按流程编号检索日志",
                        status_code=500,
                    ),
                )
                return

            _mark_step_completed(
                db,
                run.id,
                step.id,
                outcome.task_id,
                outcome.output_id,
                outcome.detail,
            )
            if step.step_type == WorkflowStepType.COLLECTION.value:
                collected_snapshot_id = outcome.output_id
            elif step.step_type == WorkflowStepType.ANALYSIS.value:
                analysis_report_id = outcome.output_id
            elif step.step_type in (
                WorkflowStepType.LYRICS.value,
                WorkflowStepType.REVIEW.value,
            ):
                lyrics_version_id = outcome.output_id

        completed_run = db.get(WorkflowRun, run.id)
        if completed_run is None:
            return
        completed_run.status = TaskStatus.COMPLETED.value
        completed_run.current_step = None
        completed_run.completed_at = utc_now()
        db.commit()
        task_logger.info(
            "workflow_run_completed",
            extra={"task_id": str(run.id), "task_type": "workflow"},
        )


def _execute_step(
    db: Session,
    run: WorkflowRun,
    step: WorkflowRunStep,
    configuration: WorkflowConfiguration,
    *,
    collected_snapshot_id: int | None,
    analysis_report_id: int | None,
    lyrics_version_id: int | None,
) -> _StepOutcome:
    step_type = step.step_type
    if run.requested_by_id is None or db.get(User, run.requested_by_id) is None:
        raise AppException(
            code="WORKFLOW_REQUESTER_NOT_FOUND",
            message="启动流程的账号已经不存在",
            status_code=409,
        )

    if step_type == WorkflowStepType.COLLECTION.value:
        collection_limit = configuration.collection.limit
        if configuration.collection.chart == "rising":
            collection_limit = max(
                collection_limit,
                configuration.collection.rising_rank,
            )
        result = create_collection(
            db,
            CollectionCreateRequest(
                source_mode=configuration.collection.source_mode,
                chart=configuration.collection.chart,
                limit=collection_limit,
            ),
            run.requested_by_id,
        )
        return _StepOutcome(result.id, result.snapshot_id)

    if step_type == WorkflowStepType.ANALYSIS.value:
        entry_ids: list[int] = []
        reference_entry_id = configuration.reference.source_entry_id
        if reference_entry_id is not None:
            reference_entry = db.get(RankingEntry, reference_entry_id)
            if reference_entry is None:
                raise AppException(
                    code="MUSIC_REFERENCE_SONG_NOT_FOUND",
                    message="参考歌曲不存在或采集记录已经过期",
                    status_code=404,
                )
            entry_ids = [reference_entry.id]
        elif collected_snapshot_id is not None:
            entry_query = select(RankingEntry.id).where(
                RankingEntry.snapshot_id == collected_snapshot_id
            )
            if configuration.collection.chart == "rising":
                target_rank = configuration.collection.rising_rank
                target_entry_id = db.scalar(
                    entry_query.where(RankingEntry.rank == target_rank).limit(1)
                )
                if target_entry_id is None:
                    raise AppException(
                        code="WORKFLOW_RISING_RANK_NOT_FOUND",
                        message=f"飙升榜没有采集到第 {target_rank} 名，无法继续分析",
                        status_code=409,
                        detail={"rising_rank": target_rank},
                    )
                entry_ids = [target_entry_id]
            else:
                entry_ids = list(
                    db.scalars(entry_query.order_by(RankingEntry.rank).limit(30)).all()
                )
        result = create_analysis(
            db,
            AnalysisCreateRequest(
                entry_ids=entry_ids,
                window_days=(
                    1
                    if configuration.collection.chart == "rising"
                    and reference_entry_id is None
                    else configuration.analysis.window_days
                ),
            ),
            run.requested_by_id,
        )
        return _StepOutcome(result.id, result.report.id if result.report else None)

    if step_type == WorkflowStepType.LYRICS.value:
        if analysis_report_id is None:
            raise AppException(
                code="WORKFLOW_ANALYSIS_OUTPUT_MISSING",
                message="分析步骤没有产出报告，无法继续作词",
                status_code=409,
            )
        delay_seconds = max(0.0, settings.WORKFLOW_STEP_DELAY_SECONDS)
        if delay_seconds:
            time.sleep(delay_seconds)
        report = db.get(AnalysisReport, analysis_report_id)
        if report is None:
            raise AppException(
                code="WORKFLOW_ANALYSIS_OUTPUT_MISSING",
                message="分析报告不存在或已经过期，无法继续作词",
                status_code=409,
            )
        if not report.creation_directions:
            raise AppException(
                code="WORKFLOW_DIRECTION_NOT_FOUND",
                message="分析报告没有可用的首选创作方向，无法继续作词",
                status_code=422,
                detail={"analysis_report_id": analysis_report_id},
            )
        index = 0
        direction = report.creation_directions[index]
        theme_keywords = list(direction.get("theme_keywords") or [])
        theme = (
            configuration.lyrics.theme
            or "、".join(str(value) for value in theme_keywords[:3])
            or str(direction.get("name") or "根据榜单趋势创作")
        )
        result = create_lyrics_task(
            db,
            LyricsCreateRequest(
                analysis_report_id=analysis_report_id,
                direction_index=index,
                title_hint=configuration.lyrics.title_hint,
                theme=theme,
                language=configuration.lyrics.language,
                requirements=configuration.lyrics.requirements,
            ),
            run.requested_by_id,
        )
        output_id = result.versions[-1].id if result.versions else None
        return _StepOutcome(result.id, output_id)

    if step_type == WorkflowStepType.REVIEW.value:
        return _execute_review_step(
            db,
            run,
            step,
            configuration,
            lyrics_version_id=lyrics_version_id,
        )

    if step_type == WorkflowStepType.MUSIC.value:
        if lyrics_version_id is None:
            raise AppException(
                code="WORKFLOW_LYRICS_OUTPUT_MISSING",
                message="作词步骤没有产出歌词版本，无法继续生成音乐",
                status_code=409,
            )
        music_task = create_music_task(
            db,
            MusicCreateRequest(
                lyrics_version_id=lyrics_version_id,
                title=configuration.music.title,
                style_prompt=configuration.music.style_prompt,
                instrumental=configuration.music.instrumental,
                requirements=configuration.music.requirements,
            ),
            run.requested_by_id,
        )
        dispatch_music_task(db, music_task.id)
        completed_task = wait_for_music_task_completion(db, music_task.id)
        if completed_task.status == TaskStatus.FAILED.value:
            raise AppException(
                code=completed_task.error_code or "SUNO_PROVIDER_FAILED",
                message=completed_task.error_message or "Suno 音乐生成失败",
                status_code=502,
                detail={
                    "task_id": completed_task.id,
                    "provider_status": completed_task.provider_status,
                },
            )
        output_id = completed_task.results[0].id if completed_task.results else None
        return _StepOutcome(completed_task.id, output_id)

    raise AppException(
        code="WORKFLOW_STEP_UNSUPPORTED",
        message="流程包含当前版本不支持的步骤",
        status_code=422,
        detail={"step_type": step_type},
    )


def _reference_requirements(instruction: str | None) -> str:
    if instruction:
        return f"{REFERENCE_DEFAULT_REQUIREMENTS}\n用户补充要求：{instruction}"
    return REFERENCE_DEFAULT_REQUIREMENTS


def _execute_review_step(
    db: Session,
    run: WorkflowRun,
    step: WorkflowRunStep,
    configuration: WorkflowConfiguration,
    *,
    lyrics_version_id: int | None,
) -> _StepOutcome:
    agent_id = configuration.review.agent_id
    if agent_id is None:
        raise AppException(
            code="WORKFLOW_REVIEW_AGENT_REQUIRED",
            message="歌词审核步骤没有配置审核智能体",
            status_code=422,
        )
    if run.requested_by_id is None:
        raise AppException(
            code="WORKFLOW_REQUESTER_NOT_FOUND",
            message="启动流程的账号已经不存在",
            status_code=409,
        )
    requester = db.get(User, run.requested_by_id)
    if requester is None:
        raise AppException(
            code="WORKFLOW_REQUESTER_NOT_FOUND",
            message="启动流程的账号已经不存在",
            status_code=409,
        )
    review_agent = require_review_agent_access(db, agent_id, requester)
    current_version_id = step.output_id or lyrics_version_id
    current_version = (
        db.get(LyricsVersion, current_version_id)
        if current_version_id is not None
        else None
    )
    if current_version is None:
        raise AppException(
            code="WORKFLOW_LYRICS_OUTPUT_MISSING",
            message="作词步骤没有可供审核的歌词版本",
            status_code=409,
        )

    detail = dict(step.result_detail or {})
    resume_action = detail.pop("resume_action", None)
    resume_instruction = str(detail.pop("resume_instruction", "") or "").strip()
    if resume_action == "regenerate":
        regenerate_lyrics(db, current_version.task_id)
        current_version = _latest_lyrics_version(db, current_version.task_id)
    elif resume_action == "revise":
        previous_feedback = _latest_review_feedback(detail)
        preview = create_lyrics_assistant_preview(
            db,
            current_version.id,
            LyricsAssistantMessageRequest(
                instruction=_review_revision_instruction(
                    previous_feedback,
                    review_agent.pass_score,
                    resume_instruction,
                )
            ),
            requester.id,
        )
        current_version = db.get(
            LyricsVersion,
            confirm_lyrics_assistant_preview(db, preview.id).id,
        )
    elif resume_action == "retry":
        current_version = _latest_lyrics_version(db, current_version.task_id)
    if current_version is None:
        raise AppException(
            code="WORKFLOW_LYRICS_OUTPUT_MISSING",
            message="歌词修改或重新生成后没有得到可审核版本",
            status_code=409,
        )
    _wait_between_text_calls()

    cycles = [
        dict(value)
        for value in list(detail.get("cycles") or [])
        if isinstance(value, dict)
    ]
    cycle: dict[str, object] = {
        "cycle": len(cycles) + 1,
        "started_lyrics_version_id": current_version.id,
        "rounds": [],
    }
    pass_score = review_agent.pass_score
    review_instruction = (
        f"这是自动流程第 {len(cycles) + 1} 次歌词审核，当前审核智能体的及格线为 "
        f"{pass_score} 分。请严格按长期记忆中的标准评分，不要为了通过而虚高分数。"
    )
    if configuration.review.instruction:
        review_instruction += f" 补充审核要求：{configuration.review.instruction}"
    review = create_lyrics_review(
        db,
        agent_id,
        ReviewCreateRequest(
            lyrics_version_id=current_version.id,
            instruction=review_instruction,
        ),
        requester,
    )
    latest_score = _review_score(review.result)
    round_detail: dict[str, object] = {
        "round": 1,
        "review_run_id": review.id,
        "lyrics_version_id": current_version.id,
        "score": latest_score,
        "summary": str(review.result.get("summary") or ""),
        "deduction_reasons": _string_list(review.result.get("deduction_reasons")),
        "revision_suggestions": _string_list(
            review.result.get("revision_suggestions")
        ),
    }
    cycle["rounds"] = [round_detail]
    if latest_score >= pass_score:
        cycle["status"] = "passed"
        cycles.append(cycle)
        return _StepOutcome(
            task_id=review.id,
            output_id=current_version.id,
            detail={
                **detail,
                "status": "passed",
                "agent_id": agent_id,
                "pass_score": pass_score,
                "latest_score": latest_score,
                "latest_lyrics_version_id": current_version.id,
                "cycles": cycles,
            },
        )

    cycle["status"] = "decision_required"
    cycles.append(cycle)
    pause_detail = {
        **detail,
        "status": "decision_required",
        "agent_id": agent_id,
        "pass_score": pass_score,
        "latest_score": latest_score,
        "latest_review_run_id": review.id,
        "latest_lyrics_version_id": current_version.id,
        "latest_deduction_reasons": round_detail["deduction_reasons"],
        "latest_revision_suggestions": round_detail["revision_suggestions"],
        "cycles": cycles,
    }
    raise _WorkflowReviewPause(
        _StepOutcome(review.id, current_version.id, pause_detail),
        f"歌词审核得分 {latest_score}，未达到 {pass_score} 分，流程已暂停等待人工判断",
    )


def _latest_lyrics_version(db: Session, task_id: int) -> LyricsVersion:
    version = db.scalar(
        select(LyricsVersion)
        .where(LyricsVersion.task_id == task_id)
        .order_by(LyricsVersion.version_number.desc(), LyricsVersion.id.desc())
        .limit(1)
    )
    if version is None:
        raise AppException(
            code="WORKFLOW_LYRICS_OUTPUT_MISSING",
            message="作词任务没有可用歌词版本",
            status_code=409,
        )
    return version


def _review_score(result: dict[str, object]) -> int:
    value = result.get("overall_score")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AppException(
            code="WORKFLOW_REVIEW_SCORE_INVALID",
            message="审核智能体没有返回有效总分",
            status_code=502,
        )
    return max(0, min(100, int(value)))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _latest_review_feedback(detail: dict[str, object]) -> dict[str, object]:
    cycles = detail.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        return {}
    latest_cycle = cycles[-1]
    if not isinstance(latest_cycle, dict):
        return {}
    rounds = latest_cycle.get("rounds")
    if not isinstance(rounds, list) or not rounds or not isinstance(rounds[-1], dict):
        return {}
    return dict(rounds[-1])


def _review_revision_instruction(
    result: dict[str, object],
    pass_score: int,
    extra_instruction: str = "",
) -> str:
    score = _review_score(result) if "overall_score" in result else int(
        result.get("score") or 0
    )
    summary = str(result.get("summary") or "").strip()
    deductions = _string_list(result.get("deduction_reasons"))
    suggestions = _string_list(result.get("revision_suggestions"))
    parts = [
        f"上一轮歌词审核总分为 {score}，及格线为 {pass_score}。",
        f"审核总结：{summary}" if summary else "",
        f"扣分原因：{'；'.join(deductions)}" if deductions else "",
        f"请逐项落实以下修改建议：{'；'.join(suggestions)}" if suggestions else "",
        f"用户补充要求：{extra_instruction}" if extra_instruction else "",
        "请保持主题与原创性，重点改进被扣分的韵律、结构、可唱性和表达，输出完整歌词。",
    ]
    return "\n".join(part for part in parts if part)[:2000]


def _wait_between_text_calls() -> None:
    delay_seconds = max(0.0, settings.WORKFLOW_STEP_DELAY_SECONDS)
    if delay_seconds:
        time.sleep(delay_seconds)


def _mark_step_running(
    db: Session,
    run_id: int,
    step_id: int,
    step_type: str,
) -> None:
    run = db.get(WorkflowRun, run_id)
    step = db.get(WorkflowRunStep, step_id)
    if run is None or step is None:
        return
    now = utc_now()
    run.current_step = step_type
    step.status = TaskStatus.RUNNING.value
    step.started_at = now
    step.completed_at = None
    step.error_code = None
    step.error_message = None
    db.commit()


def _mark_step_completed(
    db: Session,
    run_id: int,
    step_id: int,
    task_id: int,
    output_id: int | None,
    detail: dict[str, object] | None = None,
) -> None:
    run = db.get(WorkflowRun, run_id)
    step = db.get(WorkflowRunStep, step_id)
    if run is None or step is None:
        return
    step.status = TaskStatus.COMPLETED.value
    step.task_id = task_id
    step.output_id = output_id
    step.result_detail = detail
    step.error_code = None
    step.error_message = None
    step.completed_at = utc_now()
    db.commit()


def _mark_workflow_paused(
    db: Session,
    run_id: int,
    step_id: int,
    pause: _WorkflowReviewPause,
) -> None:
    db.rollback()
    run = db.get(WorkflowRun, run_id)
    step = db.get(WorkflowRunStep, step_id)
    if run is None or step is None:
        return
    code = "WORKFLOW_REVIEW_DECISION_REQUIRED"
    step.status = TaskStatus.PAUSED.value
    step.task_id = pause.outcome.task_id
    step.output_id = pause.outcome.output_id
    step.result_detail = pause.outcome.detail
    step.error_code = code
    step.error_message = pause.message
    step.completed_at = None
    run.status = TaskStatus.PAUSED.value
    run.current_step = WorkflowStepType.REVIEW.value
    run.error_code = code
    run.error_message = pause.message
    run.error_detail = pause.outcome.detail
    run.completed_at = None
    db.commit()
    task_logger.info(
        "workflow_review_paused",
        extra={
            "task_id": str(run.id),
            "task_type": "workflow",
            "step_type": step.step_type,
            "error_code": code,
        },
    )


def _mark_workflow_failed(
    db: Session,
    run_id: int,
    step_id: int,
    error: AppException,
) -> None:
    db.rollback()
    run = db.get(WorkflowRun, run_id)
    step = db.get(WorkflowRunStep, step_id)
    if run is None or step is None:
        return
    now = utc_now()
    detail = error.detail if isinstance(error.detail, dict) else None
    task_id = detail.get("task_id") if detail else None
    step.status = TaskStatus.FAILED.value
    step.task_id = task_id if isinstance(task_id, int) else step.task_id
    step.error_code = error.code
    step.error_message = error.message
    step.completed_at = now
    run.status = TaskStatus.FAILED.value
    run.error_code = error.code
    run.error_message = error.message
    run.error_detail = detail
    run.completed_at = now
    db.commit()
    task_logger.warning(
        "workflow_run_failed",
        extra={
            "task_id": str(run.id),
            "task_type": "workflow",
            "step_type": step.step_type,
            "error_code": error.code,
        },
    )


def recover_stale_workflow_runs(db: Session) -> int:
    cutoff = utc_now() - timedelta(
        seconds=max(60.0, settings.WORKFLOW_STALE_SECONDS)
    )
    runs = db.scalars(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.steps))
        .where(
            WorkflowRun.status.in_(
                (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
            ),
            func.coalesce(WorkflowRun.started_at, WorkflowRun.created_at) < cutoff,
        )
    ).all()
    if not runs:
        return 0

    now = utc_now()
    for run in runs:
        run.status = TaskStatus.FAILED.value
        run.error_code = "WORKFLOW_TASK_INTERRUPTED"
        run.error_message = "自动流程超过最长运行时间，可能因后端重启而中断，请重新运行"
        run.error_detail = {
            "reason": "workflow_runtime_exceeded",
            "max_runtime_seconds": round(settings.WORKFLOW_STALE_SECONDS),
        }
        run.completed_at = now
        active_step = next(
            (
                step
                for step in run.steps
                if step.status in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
            ),
            None,
        )
        if active_step is not None:
            active_step.status = TaskStatus.FAILED.value
            active_step.error_code = "WORKFLOW_TASK_INTERRUPTED"
            active_step.error_message = run.error_message
            active_step.completed_at = now
    db.commit()
    return len(runs)
