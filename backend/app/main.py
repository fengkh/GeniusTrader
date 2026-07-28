from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.error_handlers import (
    app_error_handler,
    internal_error_handler,
    sqlalchemy_error_handler,
    validation_error_handler,
)
from app.api.router import api_router
from app.core.config import get_settings
from app.core.csrf import CsrfProtectionMiddleware
from app.core.errors import AppError
from app.core.logging import RequestLoggingMiddleware, setup_logging
from app.core.release_gate import validate_production_startup_settings
from app.core.security_headers import SecurityHeadersMiddleware

settings = get_settings()
validate_production_startup_settings(settings)
setup_logging(settings.log_level)

app = FastAPI(title=settings.app_name)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CsrfProtectionMiddleware)
app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=settings.is_production)
if settings.trusted_host_list and "*" not in settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID", "X-CSRF-Token"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, internal_error_handler)

app.include_router(api_router)
