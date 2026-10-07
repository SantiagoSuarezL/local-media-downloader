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

`Sesión 16 — 2026-10-07 — opencode/muse-spark (fix resize + verificación) vía OpenCode`

- HANDOFF Fase 14/resize: ruff E501 + 9 failed (378 passed). Raíz: `parse_resize` sin cotas y case-fold total (aceptaba `1280X720`/`99999x99999`); planner no rechazaba presets Fase 13 ni audio-only (resize se perdía en silencio); executor perdía resize cuando había trim (trim ganaba, sin combined); `_check_resized` solo validaba `Np`, no bbox; test de dimensiones asumía deformación exacta en vez de bbox.
- Fix quirúrgico: `parse_resize` con cotas (Np 1..4320, WxH 1..8192, `x` minúscula + `p` case-insensitive, fail-fast); planner rechaza resize en presets/audio-only/live; ffmpeg bbox (`force_original_aspect_ratio=decrease:force_divisible_by=2`, helper `_scale_filter`) + `_check_resized` valida Np y bbox (fits + touches ±2px) + `transcode_trimmed(resize_target)` single-pass; executor combinado trim+resize (exige `ResizeTool`, audio+resize rechazado); E501 partido.
- Tests: borrados con aprobación explícita del usuario `test_rejects_resize_until_phase_14` y `test_resize_is_still_rejected` (invariante temporal que Fase 14 reemplaza; resto intacto); `test_resize.py` nuevo: bbox 960x720 para 4:3, +4 audio-only, +1 trim+resize single-pass. DTO sin cambios → sin sync frontend.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 390 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 501 tests.
- Decisiones usuario: borrar (no reescribir) tests temporales — reescribir duplica cobertura de `test_resize.py`, borrar es limpio porque eran gates `until_phase_14`/`still_rejected`; bbox preserva aspect (nunca deforma).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
