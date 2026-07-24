from fastapi import APIRouter

from app.api.routes import (
    admin_users,
    ai_providers,
    auth,
    daily_reviews,
    health,
    information,
    notifications,
    stocks,
    watchlist,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(ai_providers.router, prefix="/ai/providers", tags=["ai-providers"])
api_router.include_router(information.router, prefix="/information", tags=["information"])
api_router.include_router(daily_reviews.router, prefix="/reviews", tags=["daily-reviews"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    notifications.preferences_router,
    prefix="/notification-preferences",
    tags=["notification-preferences"],
)
