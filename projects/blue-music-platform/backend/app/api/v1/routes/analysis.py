from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession, require_agent_permission
from app.models import AgentType, User
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisTaskListResponse,
    AnalysisTaskResponse,
)
from app.services.analysis import create_analysis, get_analysis_task, list_analysis_tasks


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


@router.get("/tasks/{task_id}", response_model=AnalysisTaskResponse)
def analysis_detail(
    task_id: int,
    db: DatabaseSession,
    user: CurrentUser,
) -> AnalysisTaskResponse:
    return get_analysis_task(db, task_id)
