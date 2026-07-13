from fastapi import APIRouter

from app.api.v1.routes import auth, dashboard, health, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(users.router, tags=["user-management"])
