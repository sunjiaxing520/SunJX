from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, require_agent_permission
from app.models import AgentType, User
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisTaskDeleteRequest,
    AnalysisTaskDeleteResponse,
    AnalysisTaskListResponse,
    AnalysisTaskResponse,
)
from app.services.analysis import (
    create_analysis,
    delete_analysis_task,
    delete_analysis_tasks,
    get_analysis_task,
    list_analysis_tasks,
)


router = APIRouter(prefix="/analysis")
AnalysisUser = Annotated[
    User, Depends(require_agent_permission(AgentType.ANALYSIS))
]


@router.post(
    "/tasks",
    response_model=AnalysisTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_analysis(
    payload: AnalysisCreateRequest,
    db: DatabaseSession,
    user: AnalysisUser,
) -> AnalysisTaskResponse:
    return create_analysis(db, payload, user.id)


@router.get("/tasks", response_model=AnalysisTaskListResponse)
def analysis_history(
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=15, ge=1, le=100),
) -> AnalysisTaskListResponse:
    return list_analysis_tasks(db, limit)


@router.delete("/tasks", response_model=AnalysisTaskDeleteResponse)
def analysis_bulk_delete(
    payload: AnalysisTaskDeleteRequest,
    db: DatabaseSession,
    user: AnalysisUser,
) -> AnalysisTaskDeleteResponse:
    return delete_analysis_tasks(db, payload.task_ids)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def analysis_delete(
    task_id: int,
    db: DatabaseSession,
    user: AnalysisUser,
) -> Response:
    delete_analysis_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}", response_model=AnalysisTaskResponse)
def analysis_detail(
    task_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> AnalysisTaskResponse:
    return get_analysis_task(db, task_id)
