"""FastAPI application factory and default ASGI application."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application instance suitable for production or tests."""

    active_settings = settings or get_settings()
    application = FastAPI(
        title=active_settings.app_name,
        version="0.1.0",
        summary="Deterministic requirements traceability for the Asteria terminal",
    )
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: active_settings
    application.include_router(router)
    return application


app = create_app()
