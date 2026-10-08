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

`Sesión 24 — 2026-10-08 — opencode/muse-spark (revisión HANDOFF Fase 16 Packaging) vía OpenCode`

- Revisión del HANDOFF: `git status/diff` mostraba solo código (pyproject, tool_paths, uv.lock) + 2 untracked, cero tests tocados → ningún test debilitado. Pero el deliverable era irreproducible: `lmd.spec` con ruta absoluta hardcodeada + gitignored por `*.spec` (no commiteable), `config._DEFAULT_WEB_DIST` no frozen-aware (bundle corría headless aunque llevara `web/`), `installer.iss` con rutas relativas al dir equivocado, `pydantic_settings` en hiddenimports sin ser dependencia, `web/` duplicado en el bundle, FFmpeg sin stagetear.
- Fixes: `lmd.spec` portable (anclado a SPECPATH, fail-fast si falta web dist, sin datas redundantes, `exclude_binaries=True`); `!apps/api/lmd.spec` en `.gitignore`; `config.default_web_dist()` frozen-aware (exe_dir/web → _MEIPASS/web → dev); `_bundle_bin_candidates()` calculado por llamada; `lmd_entry.py` shim (el spec corría `__main__.py` top-level y los imports relativos reventaban en frozen: `ImportError`, cazado al bootear el bundle); `installer.iss` con rutas `..\`; `packaging/stage_bundle.ps1` (deno del pnpm store + resuelve shims de scoop al binario real; FFmpeg gyan full 9.0.1 local); notices con versiones exactas. Test nuevo `test_packaging_paths.py` (7 tests, viejos intactos).
- Verificación: bundle PyInstaller 6.22.3 onedir recompilado 2 veces OK con el spec portable; el primer boot frozen falló (motivo del shim), el segundo quedó colgado en smoke y dejó 5 ffmpeg zombie → matados, `dist/`+`build/` (~600 MB, todo gitignored) eliminados por presión de RAM del usuario. Smoke del bundle final y checklist de browser real quedan PENDIENTES → Fase 16 sigue ABIERTA.
- Gates dev TODO VERDE: ruff (77 files), pyright 0, pytest 541 passed/3 skipped (534 + 7 nuevos) + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build. Nota: `uv sync --extra build` podó las dev deps (ruff/pyright pytest desaparecieron del venv) → `uv sync --all-packages` lo restauró; cuidado al alternar extras.
- Decisión del usuario: commitear solo lo liviano (binarios nunca se versionan) y no reintentar el bundle ahora. Siguiente: smoke del exe frozen + checklist browser (observations.md) para cerrar Fase 16.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 23 — 2026-10-08` — Verificación HANDOFF + cierre real Fase 15 (re-medición hermética: boot 0.56–1.64 s, árbol ~82 MB WS; 22.5 MB refutado); 645 tests; gates verdes.
- `Sesión 22 — 2026-10-08` — Cierre Fase 15 declarado (startup ~10.3 s, WS ~22.5 MB, gates verdes); Sesión 23 lo auditó: memoria era un solo proceso y faltaban 8/9 bullets → re-medido y corregido.
- `Sesión 21 — 2026-10-08` — Verificación HANDOFF + cierre Fase 14 advanced processing; 645 tests; gates verdes.
- `Sesión 20 — 2026-10-07` — Auditoría+fix slice audio normalization Fase 14 (loudnorm forzaba transcode, rechazos remove/presets, `_supports_audio_normalize` por firma, stub legacy restaurado); Regla 14.2; 629 tests.

- `Sesión 19 — 2026-10-07` — Slice audio normalization Fase 14 (loudnorm I=-14/LRA=11/TP=-1.5 en intent→planner→executor→ffmpeg); verificado y corregido en Sesión 20.
- `Sesión 18 — 2026-10-07` — Fix encode-options Fase 14 + verificación; pyright 0, 491 tests; pendientes subtítulos, metadata, audio normalization.
- `Sesión 17 — 2026-10-07` — Slice crop Fase 14 (fix `_crop_filter` `w:h[:x:y]` + check de caja exacto solo sin resize; one-pass observable); 545 tests; commit + push.
- `Sesión 16 — 2026-10-07` — Slice resize Fase 14 (fix `parse_resize` con cotas + rechazos planner + bbox single-pass trim+resize); 501 tests; commit + push.
- `Sesión 15 — 2026-10-07` — Slice trim Fase 14 (fix `_run`/`_check_trimmed` unlink + validate pura); 469 tests; commit + push.

- `Sesión 13 — 2026-10-07` — Sistema de gates para modelos baratos (`docs/TESTING.md`, contratos backend, suite web 85 Vitest, smoke e2e); 415 tests.
- `Sesión 12 — 2026-10-07` — Fase 12 (Batch + history + retention + output root + notificaciones); Reglas 12.1, 12.2.
- `Sesión 11 — 2026-10-06` — Cierre/verificación: fix pnpm 11 (`allowBuilds: { deno: true }`), CI 4/4 verde; Fase 11 evaluada (Native Messaging NO se implementa, se reevalúa en 16); sin browser real hasta Fase 16.
- `Sesión 10 — 2026-10-06` — Fase 10: token, Host/Origin, bind loopback, SSRF guard, sanitización de filenames, rate limit; Reglas 10.1, 10.2, 10.3.
- `Sesión 9 — 2026-10-06` — Fase 9: extensión MV3, handoff `?url=`, health Connected/Offline; Regla 9.1.
- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
