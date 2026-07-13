from fastapi import APIRouter

from app.api.v1.routes import analysis, auth, dashboard, health, lyrics, rankings, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(users.router, tags=["user-management"])
api_router.include_router(rankings.router, tags=["rankings"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(lyrics.router, tags=["lyrics"])
