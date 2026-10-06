# Session Log — local-media-downloader

> MEMORIA ACTIVA. Se lee completa al inicio de sesión.
> REGLA DE ROTACIÓN (obligatoria, no opcional): al cerrar CADA sesión nueva,
> la sesión que hoy está en "ÚLTIMA SESIÓN" se comprime a 1-3 líneas y pasa a
> "HISTORIAL RELEVANTE"; el detalle completo se mueve a `session_log_archive.md`.
> Nunca debe haber más de 1 sesión en detalle completo en este archivo.
> Si este archivo supera ~150-200 líneas, la compresión no se está
> aplicando — parar y corregir antes de seguir agregando.

---

## ÚLTIMA SESIÓN (detalle completo)

`Sesión 6 — 2026-10-06 — Fase 6 completada`

- Scheduler asyncio + `DefaultExecutor`: budgets 3/2/1 por semáforos, cancelación cooperativa, retries con backoff vía RETRY_WAIT, chequeo de disco; `EventBus` SSE con replay e historia acotada; endpoints `POST /api/v1/jobs`, `GET /api/v1/jobs[/{id}]`, `POST .../cancel`, `GET /api/v1/events`.
- Bug que bloqueó el cierre: starlette 1.7 `TestClient` bufea la respuesta completa → cuelga en streams infinitos (verificado en su código). Fix: `_event_stream(bus)` a nivel módulo en `app.py`, tests consumen el generador directo (→ Regla 6.1).
- Tests: 12 nuevos (`test_scheduler.py` 6 + `test_events.py` 6); acceptance 10-jobs-acotados, progreso normalizado, cancel, retry acotado, framing SSE.
- Gates: ruff + format clean, pyright 0, pytest 175 passed / 3 live skipped. JS sin cambios.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
