from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.health import is_database_available

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        service=settings.SERVICE_NAME,
        environment=settings.ENVIRONMENT,
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
def database_health_check(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    if not is_database_available(db):
        raise AppException(
            code="DATABASE_UNAVAILABLE",
            message="数据库连接暂时不可用",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return DatabaseHealthResponse(
        status="healthy",
        database="postgresql",
        detail="database connection is available",
    )
