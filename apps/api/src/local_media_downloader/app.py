"""FastAPI application factory.

The app is a thin boundary: it wires configuration, structured logging and
diagnostic reporting. All media work lives behind adapters and a scheduler in
later phases; nothing here calls yt-dlp or FFmpeg directly.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import Settings
from .diagnostics import database_ready, detect_tools, storage_ready
from .logging_config import configure_logging, get_logger

_ERROR_NOT_FOUND = "NOT_FOUND"
_ERROR_VALIDATION = "VALIDATION_ERROR"
_ERROR_INTERNAL = "INTERNAL_ERROR"


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_data_dir()
    configure_logging(settings.log_level)
    logger = get_logger("api")

    app = FastAPI(
        title="Local Media Downloader",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
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
    def health() -> dict[str, object]:
        tools = detect_tools(timeout=settings.max_health_tool_timeout_seconds)
        db_ok, db_detail = database_ready(settings.database_path)
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
