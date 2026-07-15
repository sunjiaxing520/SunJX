import logging
import time
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
from app.schemas.lyrics import LyricsCreateRequest
from app.schemas.ranking import CollectionCreateRequest
from app.schemas.workflow import (
    WorkflowConfiguration,
    WorkflowRunDeleteResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowRunStepResponse,
    WorkflowTemplateResponse,
    WorkflowTemplateWrite,
)
from app.services.analysis import create_analysis
from app.services.lyrics import create_lyrics_task
from app.services.rankings import create_collection


task_logger = logging.getLogger(f"{LOGGER_NAME}.tasks")
STEP_AGENT = {
    WorkflowStepType.COLLECTION.value: AgentType.CRAWLER,
    WorkflowStepType.ANALYSIS.value: AgentType.ANALYSIS,
    WorkflowStepType.LYRICS.value: AgentType.LYRICS,
}


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
    permissions = set(
        db.scalars(
            select(UserAgentPermission.agent).where(
                UserAgentPermission.user_id == user.id
            )
        ).all()
    )
    missing = [step for step in steps if STEP_AGENT[step] not in permissions]
    if missing:
        raise AppException(
            code="WORKFLOW_PERMISSION_DENIED",
            message="当前账号没有所选流程步骤的使用权限",
            status_code=403,
            detail={"missing_steps": missing},
        )


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
    active_run = db.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.status.in_(
                (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
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

    template = _get_template(db, template_id)
    _ensure_step_permissions(db, user, template.steps)
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
        if run.status in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value)
    ]
    if active_ids:
        raise AppException(
            code="WORKFLOW_RUN_DELETE_CONFLICT",
            message="运行中的自动流程不能删除，请等待流程结束后重试",
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
        run.started_at = utc_now()
        db.commit()
        task_logger.info(
            "workflow_run_started",
            extra={"task_id": str(run.id), "task_type": "workflow"},
        )

        configuration = WorkflowConfiguration.model_validate(run.configuration)
        analysis_report_id: int | None = None
        collected_snapshot_id: int | None = None

        for step in sorted(run.steps, key=lambda value: value.position):
            _mark_step_running(db, run.id, step.id, step.step_type)
            try:
                task_id, output_id = _execute_step(
                    db,
                    run,
                    step.step_type,
                    configuration,
                    collected_snapshot_id=collected_snapshot_id,
                    analysis_report_id=analysis_report_id,
                )
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

            _mark_step_completed(db, run.id, step.id, task_id, output_id)
            if step.step_type == WorkflowStepType.COLLECTION.value:
                collected_snapshot_id = output_id
            elif step.step_type == WorkflowStepType.ANALYSIS.value:
                analysis_report_id = output_id

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
    step_type: str,
    configuration: WorkflowConfiguration,
    *,
    collected_snapshot_id: int | None,
    analysis_report_id: int | None,
) -> tuple[int, int | None]:
    if run.requested_by_id is None or db.get(User, run.requested_by_id) is None:
        raise AppException(
            code="WORKFLOW_REQUESTER_NOT_FOUND",
            message="启动流程的账号已经不存在",
            status_code=409,
        )

    if step_type == WorkflowStepType.COLLECTION.value:
        result = create_collection(
            db,
            CollectionCreateRequest(
                source_mode=configuration.collection.source_mode,
                limit=configuration.collection.limit,
            ),
            run.requested_by_id,
        )
        return result.id, result.snapshot_id

    if step_type == WorkflowStepType.ANALYSIS.value:
        entry_ids: list[int] = []
        if collected_snapshot_id is not None:
            entry_ids = list(
                db.scalars(
                    select(RankingEntry.id)
                    .where(RankingEntry.snapshot_id == collected_snapshot_id)
                    .order_by(RankingEntry.rank)
                    .limit(30)
                ).all()
            )
        result = create_analysis(
            db,
            AnalysisCreateRequest(
                entry_ids=entry_ids,
                window_days=configuration.analysis.window_days,
            ),
            run.requested_by_id,
        )
        return result.id, result.report.id if result.report else None

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
        index = configuration.lyrics.direction_index
        if index >= len(report.creation_directions):
            raise AppException(
                code="WORKFLOW_DIRECTION_NOT_FOUND",
                message="所选创作方向不存在，无法继续作词",
                status_code=422,
                detail={"direction_index": index},
            )
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
        return result.id, output_id

    raise AppException(
        code="WORKFLOW_STEP_UNSUPPORTED",
        message="流程包含当前版本不支持的步骤",
        status_code=422,
        detail={"step_type": step_type},
    )


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
    db.commit()


def _mark_step_completed(
    db: Session,
    run_id: int,
    step_id: int,
    task_id: int,
    output_id: int | None,
) -> None:
    run = db.get(WorkflowRun, run_id)
    step = db.get(WorkflowRunStep, step_id)
    if run is None or step is None:
        return
    step.status = TaskStatus.COMPLETED.value
    step.task_id = task_id
    step.output_id = output_id
    step.completed_at = utc_now()
    db.commit()


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
