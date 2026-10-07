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

`Sesión 20 — 2026-10-07 — opencode/moonshotai/kimi-k3 (auditoría + fix del slice audio normalization Fase 14) vía OpenCode`

- Auditoría del HANDOFF Sesión 19: gates del handoff verdes reales, pero el slice tenía 4 problemas: (1) `audio_normalize=True` con fuente copy-compatible caía en REMUX (`-c copy`) → loudnorm nunca se aplicaba (degradación silenciosa, el caso más común mp4→mp4); (2) combos `audio=remove` y presets gif/webp/sticker/mobile llevaban la key como detalle muerto en vez de rechazarse; (3) el executor pasaba `audio_normalize=` incondicional a `transcode` (rompía procesadores con firma Fase 4, compatibilidad documentada de la Regla 14.1) y lo enmascaró agregando `**kwargs` al stub `_LegacyTranscoder` (test viejo debilitado); (4) cambio ajeno de fase en `_step_from_dict` de scheduler.py.
- Fix quirúrgico: `_full_video_plan` incluye `not intent.audio_normalize` en `compatible` (fuerza TRANSCODE, igual que trim/resize/crop/encode); planner rechaza normalize para `audio=remove` y presets (UNSUPPORTED_INTENT); keys muertas fuera de REMUX/VIDEO_ONLY. Executor: `_NormalizeKwarg` TypedDict + `_supports_audio_normalize` (inspección de firma, mismo patrón que `_supports_encode_options`) — kwarg solo se reenvía si fue pedido; pedido-pero-no-soportado → UNSUPPORTED_INTENT. `_LegacyTranscoder` restaurado a su firma Fase 4 (test honesto de nuevo); `_step_from_dict` revertido a coerción `str()` (mantiene la garantía runtime de `PlanStep.detail: dict[str, str]`).
- Feature blindada con la matriz de capability que §528 de IMPLEMENTATION_PLAN exige: `tests/test_audio_normalize.py` nuevo (27 tests) — parse (bool estricto, rechaza "true"/1/None), matriz planner (fuerza transcode, copy sin la key, extract_audio, combo trim, rechazos remove/presets), forwarding executor (transcode/extract_audio, rechazo legacy + kwarg omitido en legacy), argv del adapter con ffmpeg real (loudnorm llega a transcode/extract_audio/trimmed/resize/crop; nunca con `audio_codec="none"`).
- Sin sync frontend: backend-only igual que slices trim/resize/crop/encode (la key es opcional; `OutputIntent.as_dict()` no alimenta ningún DTO de respuesta).
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 518 passed/3 skipped (fast) + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 629 tests.
- Pendientes Fase 14: subtítulos, metadata.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
