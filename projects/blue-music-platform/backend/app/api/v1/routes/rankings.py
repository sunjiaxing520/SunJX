from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, require_agent_permission
from app.models import AgentType, User
from app.schemas.ranking import (
    CollectionCreateRequest,
    CollectionTaskDeleteRequest,
    CollectionTaskDeleteResponse,
    CollectionTaskResponse,
    RankingEntryPage,
    RankingSnapshotResponse,
)
from app.services.rankings import (
    create_collection,
    delete_collection_task,
    delete_collection_tasks,
    list_collection_tasks,
    list_ranking_entries,
    list_snapshots,
)


router = APIRouter(prefix="/rankings")
CrawlerUser = Annotated[User, Depends(require_agent_permission(AgentType.CRAWLER))]


@router.post(
    "/collections",
    response_model=CollectionTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_collection(
    payload: CollectionCreateRequest,
    db: DatabaseSession,
    user: CrawlerUser,
) -> CollectionTaskResponse:
    return create_collection(db, payload, user.id)


@router.get("/collections", response_model=list[CollectionTaskResponse])
def collection_history(
    db: DatabaseSession,
    user: CrawlerUser,
    limit: int = Query(default=15, ge=1, le=100),
) -> list[CollectionTaskResponse]:
    return list_collection_tasks(db, limit)


@router.delete("/collections", response_model=CollectionTaskDeleteResponse)
def collection_bulk_delete(
    payload: CollectionTaskDeleteRequest,
    db: DatabaseSession,
    user: CrawlerUser,
) -> CollectionTaskDeleteResponse:
    return delete_collection_tasks(db, payload.task_ids)


@router.delete("/collections/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def collection_delete(
    task_id: int,
    db: DatabaseSession,
    user: CrawlerUser,
) -> Response:
    delete_collection_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/snapshots", response_model=list[RankingSnapshotResponse])
def snapshot_history(
    db: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=15, ge=1, le=30),
) -> list[RankingSnapshotResponse]:
    return list_snapshots(db, limit)


@router.get("/entries", response_model=RankingEntryPage)
def ranking_entries(
    db: DatabaseSession,
    user: CurrentUser,
    snapshot_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
) -> RankingEntryPage:
    return list_ranking_entries(db, snapshot_id, page, page_size, search)
