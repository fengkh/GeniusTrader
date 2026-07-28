from fastapi import APIRouter

from app.api.routes import (
    admin_users,
    ai_providers,
    announcement_ingestion,
    auth,
    daily_reviews,
    external_sources,
    health,
    information,
    market_data,
    notifications,
    security_master,
    stocks,
    watchlist,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(security_master.router, prefix="/security-master", tags=["security-master"])
api_router.include_router(security_master.admin_router, prefix="/admin/security-master", tags=["admin-security-master"])
api_router.include_router(market_data.router, prefix="/market-data", tags=["market-data"])
api_router.include_router(market_data.admin_router, prefix="/admin/market-data", tags=["admin-market-data"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(ai_providers.router, prefix="/ai/providers", tags=["ai-providers"])
api_router.include_router(information.router, prefix="/information", tags=["information"])
api_router.include_router(external_sources.router, prefix="/external-sources", tags=["external-sources"])
api_router.include_router(
    external_sources.providers_router,
    prefix="/announcement-providers",
    tags=["announcement-providers"],
)
api_router.include_router(
    announcement_ingestion.sync_runs_router,
    prefix="/announcement-sync-runs",
    tags=["announcement-sync-runs"],
)
api_router.include_router(
    announcement_ingestion.candidates_router,
    prefix="/announcement-candidates",
    tags=["announcement-candidates"],
)
api_router.include_router(daily_reviews.router, prefix="/reviews", tags=["daily-reviews"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    notifications.preferences_router,
    prefix="/notification-preferences",
    tags=["notification-preferences"],
)
