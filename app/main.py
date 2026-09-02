"""FastAPI application factory and default ASGI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.graph_routes import router as graph_router
from app.api.retrieval_routes import router as retrieval_router
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.dependencies import RepositoryManager
from app.repositories import RepositoryConnectionError, RepositoryError


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application instance suitable for production or tests."""

    active_settings = settings or get_settings()

    manager = RepositoryManager(active_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        manager.close()

    application = FastAPI(
        title=active_settings.app_name,
        version="0.3.0",
        summary="Deterministic requirements traceability for the Asteria terminal",
        lifespan=lifespan,
    )
    application.state.repository_manager = manager
    application.include_router(router)
    application.include_router(graph_router)
    application.include_router(retrieval_router)

    @application.exception_handler(RepositoryError)
    async def repository_error_handler(_: Request, exc: RepositoryError) -> JSONResponse:
        unavailable = isinstance(exc, RepositoryConnectionError)
        return JSONResponse(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if unavailable
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            content={
                "detail": {
                    "code": (
                        "repository_unavailable" if unavailable else "repository_operation_failed"
                    ),
                    "message": "The persistence backend could not complete the operation.",
                }
            },
        )

    return application


app = create_app()
