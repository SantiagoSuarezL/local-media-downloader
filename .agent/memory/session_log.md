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

`Sesión 13 — 2026-10-07 — opencode/muse-spark vía OpenCode (PowerShell/Windows)`

- Sistema de gates para modelos baratos: nuevo `docs/TESTING.md` (orden de gates, política STOP con HANDOFF, matriz fases 13-17, pitfalls); regla 11 en IMPLEMENTATION_PLAN; §24 de TECHNICAL_SPEC apunta a TESTING.md; README suma el puntero. Sin commit todavía.
- **Backend:** `tests/test_contracts.py` (13 tests: todo ErrorCode con status explícito, key sets exactos de cada DTO, envelope único de errores; fixture con NoopExecutor para que el scheduler no toque red) + `tests/test_smoke_e2e.py` (`-m smoke`: servidor real Granian en puerto fresco + data dir temporal, handoff de token por shell/cookie, matriz de status, batch por-ítem, persistencia tras reinicio con mismo token); marker `smoke` registrado en pyproject. Hallazgo: la sonda 413 envenena el keep-alive (va última, con cliente fresco).
- **Frontend:** suite Vitest nueva en `apps/web` (85 tests: `format/presets/api/live/notify`, Zod `.strict()` en `tests/schemas.ts` — devDependency, no va al bundle — y componentes `JobCard`/`Batch`); `test` script + `resolve.conditions: ['browser']` en vite.config (sin eso `mount()` falla con lifecycle_function_unavailable); `tests/**` entra a tsconfig.app para svelte-check. `pnpm -r test` ya la incluye en CI sin cambios.
- **Gates:** pytest 308 passed/3 skipped, pyright 0, ruff check+format clean, pnpm lint/format:check/check/test/build verdes (22 vitest ext + 85 web). Total: 415 tests (412 run + 3 live opt-in).
- Observación nueva en `observations.md`: batch de 100 URLs largas (~225 KB) superaría el límite 64 KiB → 413 legítimo pero extremo; monitorear cuando crezcan los intents (Fase 13/14).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 12 — 2026-10-07` — Fase 12 (Batch + history + retention + output root + notificaciones); Reglas 12.1 (retention nunca toca `updated_at`), 12.2 (`response_model=None` con `Response`).
- `Sesión 11 — 2026-10-06` — Cierre/verificación: fix pnpm 11 (`allowBuilds: { deno: true }`), CI 4/4 verde; Fase 11 evaluada (Native Messaging NO se implementa, se reevalúa en 16); sin browser real hasta Fase 16.
- `Sesión 10 — 2026-10-06` — Fase 10: token, Host/Origin, bind loopback, SSRF guard, sanitización de filenames, rate limit; Reglas 10.1, 10.2, 10.3.
- `Sesión 9 — 2026-10-06` — Fase 9: extensión MV3, handoff `?url=`, health Connected/Offline; Regla 9.1.
- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
