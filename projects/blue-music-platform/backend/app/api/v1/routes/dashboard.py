from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import get_dashboard


router = APIRouter(prefix="/dashboard")


@router.get("", response_model=DashboardResponse)
def dashboard_summary(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> DashboardResponse:
    return get_dashboard(db, current_user)
