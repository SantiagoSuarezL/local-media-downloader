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

`Sesión 18 — 2026-10-07 — opencode/z-ai-glm-5.3 (fix encode-options + verificación) vía OpenCode`

- HANDOFF Fase 14/encode-options: pyright en rojo (2 errores en `services/executor.py`). Raíz: `VideoEncodeOptionsTool` (protocolo runtime_checkable) redeclaraba `transcode`, nombre que `MediaTool` ya tiene → isinstance sólo prueba presencia (todo MediaTool lo tiene, stubs viejos incluidos → guardián muerto, bug latente) y en la intersección el unpack `**_EncodeKwargs` no matcheaba la firma de MediaTool. Pyright señalaba un bug real, no ruido. → **Regla de Oro 14.1**.
- Fix quirúrgico (solo executor.py): `_supports_encode_options()` verifica la firma real con `inspect.signature(processor.transcode).parameters` (keywords `video_bitrate`/`video_framerate`); la llamada va por `cast(VideoEncodeOptionsTool, ...)` con una única rama TRANSCODE (if/else duplicado eliminado); el protocolo dejó de ser `runtime_checkable` y su docstring documenta por qué. `intent.py`: comentario obsoleto de `video_codec` actualizado. Cero tests viejos tocados.
- Tests nuevos en `test_encode.py` (blinden el diseño): executor forwardea bitrate/framerate a un processor con firma extendida; processor legacy + sin opciones → transcode normal sigue; processor legacy + opciones → `UNSUPPORTED_INTENT` sin llamada.
- Slice verificado sin debilitar nada: planner emite `video_codec` base (`libvpx-vp9` webm / `libx264` resto) que `**encode` sobreescribe solo con codec explícito — tests del modelo barato ya eran consistentes; no hizo falta tocar planner. DTO crece (`video_bitrate`/`video_framerate` opcionales) pero no está expuesto en `_job_dict` → sin sync de `test_contracts.py`/`schemas.ts`; `packages/contracts/src/index.ts` ya actualizado.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 491 passed/3 skipped + smoke 1 passed (ffmpeg local tiene libsvtav1 → tests av1 corren), pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 605 tests.
- Pendientes Fase 14: subtítulos, metadata, audio normalization.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 17 — 2026-10-07` — Slice crop Fase 14 (fix `_crop_filter` `w:h[:x:y]` + check de caja exacto solo sin resize; one-pass observable); 545 tests; commit + push.
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
