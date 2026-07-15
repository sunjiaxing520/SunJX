from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.workflow import (
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowTemplateResponse,
    WorkflowTemplateWrite,
)
from app.services.workflows import (
    create_workflow_template,
    delete_workflow_template,
    execute_workflow_run,
    get_workflow_run,
    list_workflow_runs,
    list_workflow_templates,
    start_workflow_run,
    update_workflow_template,
)


router = APIRouter(prefix="/workflows")


@router.get("/templates", response_model=list[WorkflowTemplateResponse])
def template_list(
    db: DatabaseSession,
    user: CurrentUser,
) -> list[WorkflowTemplateResponse]:
    return list_workflow_templates(db)


@router.post(
    "/templates",
    response_model=WorkflowTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def template_create(
    payload: WorkflowTemplateWrite,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkflowTemplateResponse:
    return create_workflow_template(db, payload, user)


@router.put("/templates/{template_id}", response_model=WorkflowTemplateResponse)
def template_update(
    template_id: int,
    payload: WorkflowTemplateWrite,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkflowTemplateResponse:
    return update_workflow_template(db, template_id, payload, user)


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def template_delete(
    template_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> Response:
    delete_workflow_template(db, template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/templates/{template_id}/runs",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_start(
    template_id: int,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkflowRunResponse:
    run = start_workflow_run(db, template_id, user)
    background_tasks.add_task(execute_workflow_run, run.id, db.get_bind())
    return run


@router.get("/runs", response_model=WorkflowRunListResponse)
def run_list(
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=15, ge=1, le=100),
) -> WorkflowRunListResponse:
    return list_workflow_runs(db, limit)


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def run_detail(
    run_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkflowRunResponse:
    return get_workflow_run(db, run_id)
