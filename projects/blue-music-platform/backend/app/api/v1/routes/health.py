from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database connection is unavailable",
        )

    return DatabaseHealthResponse(
        status="healthy",
        database="postgresql",
        detail="database connection is available",
    )
