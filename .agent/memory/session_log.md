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

`Sesión 12 — 2026-10-07 — opencode/muse-spark vía OpenCode (PowerShell/Windows)`

- Fase 12 (Batch + history) implementada completa, backend + web. Sin commit todavía (pendiente decisión del usuario).
- **Dominio nuevo:** `domain/urls.py::normalize_url` (lowercase scheme/host, sin puerto default, sin fragment, sin tracking params, query ordenada); `domain/dedupe.py` (`intent_fingerprint` con JSON canonical + `dedupe_key = sha256(url_norm + intent)`); `domain/output.py` (reglas cerradas `flat`/`by_extractor`/`by_date`, sanitización por segmento, prueba de contención).
- **Schema v3:** columna `dedupe_key` + `idx_jobs_dedupe` + `idx_jobs_updated_at`; test de upgrade v2→v3 en `test_db.py` (filas viejas leen con key NULL y nunca matchean).
- **Repositorio (`jobs.py`):** `create_job` acepta `dedupe_key`; `find_duplicate` (misma key + estado no-terminal; COMPLETED/FAILED/CANCELLED no cuentan); `clear_source_url` (NO toca `updated_at` → Regla 12.1); `delete_job`; `list_terminal_older_than`; `set_priority`; `reset_for_retry` (resetea intentos+errores, devuelve el job).
- **State machine:** `CANCELLED → RETRY_WAIT` agregado (retry manual de cancelados accidentales; COMPLETED sigue terminal).
- **Servicios:** `services/retention.py` (3 relojes sobre `updated_at`: `source_url_retention`, `temporary_retention_hours`, `history_retention_days`; sweep al startup + cada 6 h + endpoint manual; nunca crashea el sweep); `services/batch.py` (async, por-item: intent → rate limit → resolve en thread → plan → dedupe → create; publica `batch_submitted`). Notificaciones: sin servicio nuevo — el dashboard usa los eventos SSE existentes + Notification API (opt-in, `lib/notify.ts`).
- **API:** `POST /jobs/batch` (1–100 items, resultados por índice), dedupe también en `POST /jobs` single (200 + `"duplicate": true`, resolve pasa a `asyncio.to_thread`), `POST /jobs/{id}/retry` (FAILED/CANCELLED/RECOVERY_REQUIRED; 409 si URL redactada), `POST /jobs/{id}/priority` (±100), `GET /jobs` con `limit/cursor/states` + `next_cursor` (cursor base64url; `response_model=None` → Regla 12.2), `POST /maintenance/cleanup`, `PATCH /settings` (solo claves runtime, `extra="forbid"`).
- **Executor:** el output final va a `output_root` con la regla configurada (`LMD_OUTPUT_ROOT`, default `~/Downloads/Local Media Downloader`; `LMD_OUTPUT_RULE`); `data_dir/output` como fallback en tests. `bandwidth_limit_bps` solo reservado (reportado, no enforceado).
- **Web:** pantalla Batch (textarea multi-URL + preset + prioridad + tabla de resultados), History con paginación/Load more + Retry por fila + Run cleanup, JobDetails con Retry + editor de prioridad, Settings con sección editable de retention/output + toggle de notificaciones; `lib/presets.ts` compartido (Resolve refactorizado a usarlo).
- **Gates:** pytest 294 passed/3 skipped, pyright 0, ruff check+format clean, pnpm lint/format:check/check/test/build verdes (22 vitest). Reglas nuevas 12.1, 12.2; 9.1 archivada por rotación.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 11 — 2026-10-06` — Cierre/verificación: fix pnpm 11 (`allowBuilds: { deno: true }`), CI 4/4 verde; Fase 11 evaluada (Native Messaging NO se implementa, se reevalúa en 16); sin browser real hasta Fase 16.
- `Sesión 10 — 2026-10-06` — Fase 10: token, Host/Origin, bind loopback, SSRF guard, sanitización de filenames, rate limit; Reglas 10.1, 10.2, 10.3.
- `Sesión 9 — 2026-10-06` — Fase 9: extensión MV3, handoff `?url=`, health Connected/Offline; Regla 9.1.
- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
