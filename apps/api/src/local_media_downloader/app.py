"""FastAPI application factory.

The app is a thin boundary: it wires configuration, structured logging and
diagnostic reporting. All media work lives behind adapters and a scheduler in
later phases; nothing here calls yt-dlp or FFmpeg directly.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .adapters.yt_dlp import YtDlpExtractor
from .config import Settings
from .db import initialize, schema_version
from .diagnostics import detect_tools, storage_ready
from .domain.errors import ExtractionError
from .domain.extractor import Extractor
from .logging_config import configure_logging, get_logger
from .services.resolve import ResolveService, error_response

_ERROR_NOT_FOUND = "NOT_FOUND"
_ERROR_VALIDATION = "VALIDATION_ERROR"
_ERROR_INTERNAL = "INTERNAL_ERROR"

# A deliberately conservative floor, not the pinned version: the point is to
# warn when the installed extractor set is old enough that site breakage is
# likely. The pinned version lives in uv.lock; this is the "too old to trust"
# line and it only ever moves forward.
_MINIMUM_YTDLP_VERSION = (2026, 1, 1)

# The service binds to loopback only: there is no CDN and nothing to cache for.
# Every response is live state (jobs, progress, settings), so an intermediary
# cache would show the user a stale job — the opposite of what the SSE stream
# promises. `no-store` also keeps media URLs and error detail out of browser
# caches on a shared machine.
_NO_STORE = {"Cache-Control": "no-store"}


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


class ResolveRequest(BaseModel):
    """Strict input schema: the API is a security boundary (#18)."""

    url: str = Field(min_length=1, max_length=2048)


def _database_status(conn: sqlite3.Connection | None) -> tuple[bool, str]:
    """Report the real database, not a probe: the schema must be reachable."""
    if conn is None:
        return False, "not initialized"
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        return False, f"unreachable: {exc}"
    return True, f"ok (schema v{schema_version(conn)})"


def _extractor_status(make_extractor: Callable[[], Extractor]) -> dict[str, object]:
    """yt-dlp version plus the outdated signal the spec requires.

    Extractors break when platforms change, so diagnostics must be able to say
    "this may be outdated" without attempting an update: updates are an
    explicit user action, never automatic (TECHNICAL_SPEC §1).
    """
    extractor = make_extractor()
    version = extractor.version
    if version is None:
        return {
            "name": extractor.name,
            "available": False,
            "version": None,
            "may_be_outdated": None,
        }
    try:
        current = tuple(int(part) for part in version.split("."))
    except ValueError:
        return {
            "name": extractor.name,
            "available": True,
            "version": version,
            "may_be_outdated": None,
        }
    may_be_outdated = current < _MINIMUM_YTDLP_VERSION
    return {
        "name": extractor.name,
        "available": True,
        "version": version,
        "may_be_outdated": may_be_outdated,
    }


def create_app(
    settings: Settings | None = None,
    *,
    extractor_factory: Callable[[], Extractor] | None = None,
) -> FastAPI:
    """Build the application.

    ``extractor_factory`` exists so tests can inject a stub instead of spawning
    yt-dlp; production always uses :class:`YtDlpExtractor`.
    """
    settings = settings or Settings.from_env()
    make_extractor = extractor_factory or YtDlpExtractor
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

    @app.middleware("http")
    async def no_store(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Mark every API response as uncacheable (see _NO_STORE)."""
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

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
        payload["extractor"] = _extractor_status(make_extractor)
        return payload

    @app.post("/api/v1/resolve")
    def resolve(payload: ResolveRequest) -> JSONResponse:
        """Resolve a URL into normalized MediaInfo.

        This is a thin boundary: it validates, delegates to the extractor port
        and returns the normalized model. No yt-dlp syntax is ever built here.
        """
        service = ResolveService(make_extractor())
        try:
            info = service.resolve(payload.url)
        except ExtractionError as error:
            status, body = error_response(error)
            logger.info("resolve_failed", extra={"error_code": error.code.value})
            return JSONResponse(status_code=status, content=body)
        return JSONResponse(status_code=200, content=info.as_dict())

    return app


app = create_app()
