"""M1 API bootstrap. No migrations or physical actions occur on startup."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from brewery_config import database_url, web_assets_directory
from brewery_database.connection import create_database_engine, database_is_ready
from .recipe_http import install_recipe_routes


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["beer-brewing-app"] = "beer-brewing-app"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = create_database_engine(database_url())
        application.state.database = engine
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="Brewery Companion API",
        version="1.0.0",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    install_recipe_routes(application)

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @application.get(
        "/api/v1/readiness",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse, "description": "Database or schema unavailable"}},
    )
    def readiness(response: Response) -> ReadinessResponse:
        ready = database_is_ready(application.state.database)
        response.status_code = 200 if ready else 503
        return ReadinessResponse(status="ready" if ready else "unavailable")

    if (assets := web_assets_directory()) is not None:
        @application.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
        @application.api_route("/index.html", methods=["GET", "HEAD"], include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(assets / "index.html", headers={
                "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "frame-ancestors 'none'", "X-Frame-Options": "DENY",
            })

        application.mount("/assets", StaticFiles(directory=assets / "assets"), name="web-assets")

    return application
