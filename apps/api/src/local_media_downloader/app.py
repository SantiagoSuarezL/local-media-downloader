"""FastAPI application factory.

The app is a thin boundary: it wires configuration, structured logging and
diagnostic reporting. All media work lives behind adapters and a scheduler in
later phases; nothing here calls yt-dlp or FFmpeg directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, jobs
from .adapters.ffmpeg import FFmpegProcessor
from .adapters.yt_dlp import YtDlpExtractor
from .config import Settings
from .db import initialize, schema_version
from .diagnostics import detect_tools, storage_ready
from .domain.errors import ExtractionError
from .domain.extractor import Extractor
from .domain.intent import parse_intent
from .job_state import JobState
from .logging_config import configure_logging, get_logger
from .security import (
    TOKEN_HEADER,
    SecurityError,
    load_or_create_token,
    token_matches,
    validate_host,
    validate_origin,
)
from .services.events import EventBus
from .services.executor import DefaultExecutor
from .services.planner import Planner
from .services.rate_limit import RateLimiter, per_minute_limiter
from .services.recovery import recover_interrupted_jobs
from .services.resolve import ResolveService, error_response
from .services.scheduler import ExecutorProtocol, Scheduler, SchedulerLimits

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

# Endpoints the browser extension may call without a token. Health carries no
# secret (status, versions, storage); it exists so the popup can say Connected /
# Offline, and the popup cannot hold a token.
_PUBLIC_API_PATHS = frozenset({"/api/v1", "/api/v1/health"})

# Name of the HttpOnly cookie that carries the token for browser clients that
# cannot set headers (EventSource, plain navigation).
TOKEN_COOKIE = "lmd_token"

# Health is the one unauthenticated endpoint (the extension polls it), and its
# tool detection spawns subprocesses. A short cache keeps that from being a
# process-storm lever without making the indicator feel stale.
_HEALTH_CACHE_SECONDS = 5.0


class JobRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    intent: dict[str, object]
    title: str | None = None
    priority: int = 0


def _job_dict(job: jobs.Job) -> dict[str, object]:
    return {
        "id": job.id,
        "state": job.state.value,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "source_url": job.source_url,
        "title": job.title,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "output_path": job.output_path,
        "priority": job.priority,
        "attempt_count": job.attempt_count,
    }


def _error_payload(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


async def _event_stream(bus: EventBus) -> AsyncGenerator[str, None]:
    """Yield SSE frames for every bus event, replaying recent history first.

    Module-level (not a closure) so tests can consume it directly: the
    installed TestClient buffers whole responses, which hangs forever on an
    infinite stream. The endpoint below is a thin wrapper around this.
    """
    queue = bus.subscribe()
    try:
        while True:
            event = await queue.get()
            yield event.as_sse()
    finally:
        bus.unsubscribe(queue)


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


def _mount_web_ui(
    app: FastAPI, web_dist: Path, logger: logging.Logger | logging.LoggerAdapter
) -> None:
    """Serve the built Svelte UI from the same loopback origin.

    Production runs no Node server: `pnpm build` emits static assets into
    `apps/web/dist` and FastAPI serves them at `/` (IMPLEMENTATION_PLAN Phase 8).
    Mounting happens after every `/api/v1` route so the API always wins the match.
    If the build output is missing (tests, or dev with Vite on :5173) the API
    stays fully usable headless.

    The shell carries the API token in a ``HttpOnly`` cookie and a ``<meta>``
    tag: the shell is only ever served to a request that already passed the
    loopback Host check, which is what makes handing the token over safe. The
    dashboard then authenticates every call with the cookie (EventSource cannot
    set headers) or the header.
    """
    if not (web_dist / "index.html").is_file():
        logger.info("web_ui_missing", extra={"path": str(web_dist)})
        return

    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    shell_template = (web_dist / "index.html").read_text(encoding="utf-8")
    token_meta = '<meta name="lmd-token" content="{token}" />'

    @app.get("/{path:path}", include_in_schema=False)
    def web_index(request: Request, path: str) -> Response:
        """Single-page fallback: unknown non-API paths render the SPA shell.

        `/api/*` is deliberately excluded: an unknown API route must stay a
        structured 404, never the HTML shell, or clients would parse HTML as JSON.
        """
        if path == "api" or path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content=_error_payload(_ERROR_NOT_FOUND, f"unknown endpoint: /{path}"),
            )
        token = _redact_free(request.app.state.token)
        html = shell_template.replace("<head>", f"<head>{token_meta.format(token=token)}", 1)
        response = Response(html, media_type="text/html")
        # SameSite=Strict keeps the cookie off every cross-site request, so a
        # hostile page cannot ride the user's session.
        response.set_cookie(
            TOKEN_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    logger.info("web_ui_mounted", extra={"path": str(web_dist)})


def _redact_free(token: str) -> str:
    """Escape the token for safe interpolation into HTML attributes."""
    return token.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def create_app(
    settings: Settings | None = None,
    *,
    extractor_factory: Callable[[], Extractor] | None = None,
    executor_factory: Callable[[], ExecutorProtocol] | None = None,
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
        # The token lives in the settings table so it survives restarts; it is
        # registered as a secret here so no code path can log it.
        application.state.token = load_or_create_token(application.state.db)
        application.state.resolve_limiter = per_minute_limiter(
            settings.resolve_rate_limit_per_minute
        )
        bus = EventBus()
        limits = SchedulerLimits(
            max_active=settings.scheduler_max_active,
            max_downloads=settings.scheduler_max_downloads,
            max_encoders=settings.scheduler_max_encoders,
            max_attempts=settings.scheduler_max_attempts,
            retry_backoff_seconds=settings.scheduler_retry_backoff_seconds,
        )
        report = recover_interrupted_jobs(
            application.state.db,
            data_dir=settings.data_dir,
            max_attempts=limits.max_attempts,
            bus=bus,
        )
        if report.actions:
            logger.info("recovery_reconciled", extra={"jobs": len(report.actions)})
        if executor_factory is not None:
            executor = executor_factory()
        else:
            executor = DefaultExecutor(
                application.state.db,
                processor=FFmpegProcessor(),
                data_dir=settings.data_dir,
                bus=bus,
                download_sem=asyncio.Semaphore(limits.max_downloads),
                encode_sem=asyncio.Semaphore(limits.max_encoders),
            )
        scheduler = Scheduler(
            application.state.db,
            executor=executor,
            bus=bus,
            limits=limits,
            working_dir=str(settings.data_dir),
        )
        application.state.bus = bus
        application.state.scheduler = scheduler
        scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()
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
    async def security_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Treat loopback as a boundary: Host, Origin, size and token.

        Ordering matters. Host/Origin run first so a rebound or cross-origin
        request never reaches body handling, and the size check runs before the
        endpoint sees the payload.
        """
        try:
            validate_host(request.headers.get("host"), expected_port=settings.port)
            validate_origin(request.headers.get("origin"))
        except SecurityError as error:
            logger.info(
                "request_refused",
                extra={"error_code": error.code, "path": request.url.path},
            )
            return JSONResponse(
                status_code=error.status_code,
                content=_error_payload(error.code, error.message),
            )

        length = request.headers.get("content-length")
        if length is not None:
            try:
                too_large = int(length) > settings.max_request_bytes
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(
                    status_code=413,
                    content=_error_payload(
                        "REQUEST_TOO_LARGE",
                        f"The request body exceeds {settings.max_request_bytes} bytes.",
                    ),
                )

        if request.url.path.startswith("/api/") and request.url.path not in _PUBLIC_API_PATHS:
            provided = request.headers.get(TOKEN_HEADER) or request.cookies.get(TOKEN_COOKIE)
            if not token_matches(provided, request.app.state.token):
                logger.info(
                    "request_unauthenticated",
                    extra={"error_code": "UNAUTHORIZED", "path": request.url.path},
                )
                return JSONResponse(
                    status_code=401,
                    content=_error_payload("UNAUTHORIZED", "A valid local token is required."),
                )

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def no_store(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Mark every API response as uncacheable (see _NO_STORE)."""
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/v1")
    def service_root() -> dict[str, str]:
        """Service banner.

        Deliberately under `/api/v1`: the bare `/` belongs to the web UI when a
        build is present, and an API surface that changes shape depending on
        whether assets exist is worse than moving one route.
        """
        return {"service": "local-media-downloader", "health": "/api/v1/health"}

    @app.get("/api/v1/health")
    def health(request: Request) -> dict[str, object]:
        """Liveness plus tool detection.

        The only endpoint reachable without a token (the extension needs it),
        so the tool probe is cached for a few seconds: without the cache, every
        call would spawn five subprocesses and any local caller could turn that
        into a process-storm denial of service.
        """
        cached = getattr(request.app.state, "health_cache", None)
        now = time.monotonic()
        if cached is not None and now - cached[0] < _HEALTH_CACHE_SECONDS:
            return cached[1]

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
        request.app.state.health_cache = (now, payload)
        return payload

    @app.get("/api/v1/events")
    def events() -> StreamingResponse:
        """SSE stream of normalized progress and scheduler events (§3)."""
        bus: EventBus = app.state.bus
        return StreamingResponse(
            _event_stream(bus),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/v1/jobs", status_code=201)
    async def create_job_endpoint(payload: JobRequest, request: Request) -> JSONResponse:
        """Validate intent, resolve the URL, plan, and enqueue a job."""
        try:
            intent = parse_intent(payload.intent)
        except ExtractionError as error:
            status, body = error_response(error)
            return JSONResponse(status_code=status, content=body)
        try:
            service = ResolveService(make_extractor())
            info = service.resolve(payload.url)
            plan = Planner().plan(intent, info)
        except ExtractionError as error:
            status, body = error_response(error)
            return JSONResponse(status_code=status, content=body)
        job = jobs.create_job(
            request.app.state.db,
            source_url=payload.url,
            title=payload.title or info.source.title,
            priority=payload.priority,
            intent_json=json.dumps(payload.intent),
            execution_plan_json=json.dumps(plan.as_dict()),
            state=JobState.QUEUED,
        )
        scheduler: Scheduler = request.app.state.scheduler
        scheduler.wake()
        job = jobs.get_job(request.app.state.db, job.id)
        assert job is not None
        return JSONResponse(status_code=201, content=_job_dict(job))

    @app.get("/api/v1/jobs")
    def list_jobs(request: Request) -> dict[str, object]:
        found = jobs.list_jobs(request.app.state.db)
        return {"jobs": [_job_dict(job) for job in found]}

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> JSONResponse:
        job = jobs.get_job(request.app.state.db, job_id)
        if job is None:
            return JSONResponse(
                status_code=404, content=_error_payload(_ERROR_NOT_FOUND, "job not found")
            )
        return JSONResponse(status_code=200, content=_job_dict(job))

    @app.post("/api/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, request: Request) -> JSONResponse:
        scheduler: Scheduler = request.app.state.scheduler
        try:
            scheduler.request_cancel(job_id)
        except KeyError:
            return JSONResponse(
                status_code=404, content=_error_payload(_ERROR_NOT_FOUND, "job not found")
            )
        except ValueError as exc:
            return JSONResponse(status_code=409, content=_error_payload("CONFLICT", str(exc)))
        job = jobs.get_job(request.app.state.db, job_id)
        assert job is not None
        return JSONResponse(status_code=200, content=_job_dict(job))

    @app.get("/api/v1/settings")
    def get_settings() -> dict[str, object]:
        """Runtime configuration, read-only.

        Configuration comes from the environment at boot, so the API reports it
        but never mutates it: changing anything requires a restart. Nothing
        secret is exposed — only loopback/service values.
        """
        return {
            "host": settings.host,
            "port": settings.port,
            "log_level": settings.log_level,
            "data_dir": str(settings.data_dir),
            "database_path": str(settings.database_path),
            "scheduler_max_active": settings.scheduler_max_active,
            "scheduler_max_downloads": settings.scheduler_max_downloads,
            "scheduler_max_encoders": settings.scheduler_max_encoders,
            "scheduler_max_attempts": settings.scheduler_max_attempts,
            "scheduler_retry_backoff_seconds": settings.scheduler_retry_backoff_seconds,
        }

    @app.post("/api/v1/resolve")
    async def resolve(payload: ResolveRequest, request: Request) -> JSONResponse:
        """Resolve a URL into normalized MediaInfo.

        This is a thin boundary: it validates, delegates to the extractor port
        and returns the normalized model. No yt-dlp syntax is ever built here.
        Rate limited because a resolve spawns yt-dlp: a burst here is a burst of
        processes, not a burst of queries.
        """
        limiter: RateLimiter = request.app.state.resolve_limiter
        allowed, retry_after = await limiter.allow(
            request.client.host if request.client else "local"
        )
        if not allowed:
            logger.info("resolve_rate_limited")
            response = JSONResponse(
                status_code=429,
                content=_error_payload(
                    "RATE_LIMITED",
                    "Too many resolve requests; wait a moment before retrying.",
                ),
            )
            response.headers["Retry-After"] = str(max(1, int(retry_after) + 1))
            return response

        service = ResolveService(make_extractor())
        try:
            # The extractor blocks on a subprocess; keep it off the event loop.
            info = await asyncio.to_thread(service.resolve, payload.url)
        except ExtractionError as error:
            status, body = error_response(error)
            logger.info("resolve_failed", extra={"error_code": error.code.value})
            return JSONResponse(status_code=status, content=body)
        return JSONResponse(status_code=200, content=info.as_dict())

    _mount_web_ui(app, settings.web_dist, logger)
    return app


app = create_app()
