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

`Sesión 21 — 2026-10-08 — opencode/muse-spark (verificación HANDOFF + cierre Fase 14) vía OpenCode`

- Verificación del HANDOFF subtitles/metadata: `git status/diff` separó código (2 archivos: `domain/intent.py` +14, `services/planner.py` +12) vs tests (1 nuevo `tests/test_advanced_processing.py`); cero tests viejos modificados — ningún test existente fue debilitado para pasar.
- Auditoría de contrato: sin `ErrorCode` nuevo (reúsa `UNSUPPORTED_INTENT`), sin DTO de respuesta tocado (`OutputIntent.as_dict()` no alimenta `_job_dict`; `dedupe_key` usa el dict crudo del request), `presets.test.ts` sigue en su key set mínimo y `schemas.ts` no cubre el intent request → sin sync frontend, igual que los slices trim/resize/crop/encode. Rechazo temprano en `plan()` (antes de presets/audio-only) = sin detalles muertos (Regla 14.2); bool estricto en parse (Regla 14.1 no aplica: no hay extensión de firma). Sin fix necesario.
- Feature blindada con la matriz que §528 exige: `test_advanced_processing.py` (16 tests) — defaults False + `as_dict`, aceptación de flags, rechazo de no-booleanos ("true"/1/0/None/[]), planner rechaza subtitles/metadata con mensaje exacto, plan normal intacto.
- Gates TODO VERDE: ruff check + format (83 files), pyright 0, pytest 534 passed/3 skipped (fast) + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 645 tests.
- Fase 14 CERRADA en memoria (`roadmap.md` ✅, `INDEX.md` → Fase 15); `graphify update .` + commit + push. Siguiente: Fase 15 Performance engineering.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
