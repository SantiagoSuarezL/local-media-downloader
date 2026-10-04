"""FastAPI application factory.

The app is a thin boundary: it wires configuration, structured logging and
diagnostic reporting. All media work lives behind adapters and a scheduler in
later phases; nothing here calls yt-dlp or FFmpeg directly.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import Settings
from .db import initialize, schema_version
from .diagnostics import detect_tools, storage_ready
from .logging_config import configure_logging, get_logger

_ERROR_NOT_FOUND = "NOT_FOUND"
_ERROR_VALIDATION = "VALIDATION_ERROR"
_ERROR_INTERNAL = "INTERNAL_ERROR"


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


def _database_status(conn: sqlite3.Connection | None) -> tuple[bool, str]:
    """Report the real database, not a probe: the schema must be reachable."""
    if conn is None:
        return False, "not initialized"
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        return False, f"unreachable: {exc}"
    return True, f"ok (schema v{schema_version(conn)})"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_data_dir()
    configure_logging(settings.log_level)
    logger = get_logger("api")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.db = initialize(settings.database_path)
        logger.info(
            "database_ready", extra={"schema_version": schema_version(application.state.db)}
        )
        try:
            yield
        finally:
            application.state.db.close()

    app = FastAPI(
        title="Local Media Downloader",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                _ERROR_NOT_FOUND if exc.status_code == 404 else "HTTP_ERROR", str(exc.detail)
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                _ERROR_VALIDATION, str(exc.errors()[0].get("msg", "invalid request"))
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.log(40, f"unhandled error: {exc}", extra={"error_code": _ERROR_INTERNAL})
        return JSONResponse(
            status_code=500, content=_error_payload(_ERROR_INTERNAL, "internal error")
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "local-media-downloader", "health": "/api/v1/health"}

    @app.get("/api/v1/health")
    def health(request: Request) -> dict[str, object]:
        tools = detect_tools(timeout=settings.max_health_tool_timeout_seconds)
        db_ok, db_detail = _database_status(getattr(request.app.state, "db", None))
        storage_ok, storage_detail = storage_ready(settings.data_dir)
        payload: dict[str, object] = {
            "status": "ok" if db_ok and storage_ok else "degraded",
            "version": __version__,
            "api": "ok",
            "database": {"status": "ok" if db_ok else "error", "detail": db_detail},
            "storage": {"status": "ok" if storage_ok else "error", "detail": storage_detail},
            "tools": {name: tool.as_dict() for name, tool in tools.items()},
        }
        logger.info("health_check")
        return payload

    return app


app = create_app()
