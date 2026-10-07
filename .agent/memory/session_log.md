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

`Sesión 17 — 2026-10-07 — opencode/muse-spark (fix crop + verificación) vía OpenCode`

- HANDOFF Fase 14/crop: 6 failed, 428 passed. Doble raíz en `adapters/ffmpeg.py`: (1) `_crop_filter` emitía `crop=160x120` pero ffmpeg toma `w:h:x:y` con dos puntos → `Invalid chars 'x120'`; (2) tras arreglarlo, 2 fallos más — `_check_cropped` (match exacto de caja) corría sobre el archivo final del pass único crop+scale (960x720 vs caja 160x120).
- Fix quirúrgico: `_crop_filter` → `crop=w:h` / `crop=w:h:x:y`; check de caja exacto solo cuando `resize_target is None` en `crop()` y `transcode_trimmed()` (un pass único produce un solo archivo: solo la geometría final es observable; ffmpeg falla ruidoso si la caja excede el frame, y `_check_resized` sigue validando el bbox final). Orden crop-antes-de-scale intacto (caja en coords de origen). `_crop_size` sin cambios.
- Sin tests debilitados: diffs en `test_trim/test_resize` solo agregan `"crop": None` al `as_dict` (expansión de contrato por el campo nuevo de `Processing`); contratos backend + frontend ya sincronizados en el slice (ambos verdes). Los tests que blindan el fix ya existían en `test_crop.py` nuevo (exact box, offset, one-pass, trim+crop+resize).
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 434 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 545 tests.
- Pendientes Fase 14: bitrate, framerate, codec, subtítulos, metadata, audio normalization.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 16 — 2026-10-07` — Slice resize Fase 14 (fix `parse_resize` con cotas + rechazos planner + bbox single-pass trim+resize); 501 tests; commit + push.
- `Sesión 15 — 2026-10-07` — Slice trim Fase 14 (fix `_run`/`_check_trimmed` unlink + validate pura); 469 tests; commit + push.
- `Sesión 14 — 2026-10-07` — Fase 13 (presets gif/webp/sticker/mobile + VP9/Opus en webm); drill stop-on-failure validado; 439 tests; commit `b4c10cf` + push.

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
