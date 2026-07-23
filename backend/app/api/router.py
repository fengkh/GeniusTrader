from fastapi import APIRouter

from app.api.routes import admin_users, auth, health, stocks, watchlist

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
