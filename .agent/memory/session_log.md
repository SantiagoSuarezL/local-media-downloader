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

`Sesión 23 — 2026-10-08 — opencode/muse-spark (verificación HANDOFF + cierre real Fase 15) vía OpenCode`

- Verificación del HANDOFF Sesión 22: `git status/diff` solo tocaba memoria (3 archivos), cero código/tests → ningún test debilitado. Pero la medición era incompleta: script `measure_startup.py` sin commitear (puerto fijo 18765, viola Regla 10.2; pipe de stdout sin drenar; claimaba WorkingSet sin medirlo) + `data_perf_test/` vacío → ambos eliminados del repo.
- Re-medición hermética (puerto fresco con ownership, `LMD_DATA_DIR` temporal): boot→listen 0.56–1.64 s, →first `/health` 200 10–22 s (delta ~12.5 s = tool probes del health en frío); memoria del ÁRBOL 81.6–82.0 MB WS / 67–69 MB privada (3 python: launcher ~4 + Granian ~28 + worker ~49) → 22.5 MB refutado. Import app ~0.6–1.2 s (domina fastapi). API: health med 3 ms p95 17 ms; jobs-list med 3 ms p95 17 ms. Cola (in-process, stub extractor + scheduler real, n=10): pickup med 13.3 ms p95 15 ms. SQLite: 2000 inserts 155 ms single-txn / 11 ms batch, keyset page 0.041 ms. Disco 349/1377 MB/s. FFmpeg synth 480p5s 0.33 s ≈457 fps. UI `dist` 108190 B.
- No medible offline por diseño: download throughput (crear jobs resuelve vía yt-dlp real; `.invalid`→502) y cola sobre HTTP real → diferido a red en vivo (TESTING.md §5, `observations.md`). Sonda de cola casi falla por saturar `max_active=3` con executor que nunca termina (lección: liberar slot con cancel entre muestras). Tuning: SIN cambios — headroom en todos los knobs (Granian workers=1, scheduler 3/2/1, threads FFmpeg); el único costo (probes del primer health) es diagnóstico por diseño, cachearlo cambiaría el contrato → observación abierta para Fase 16/17.
- Gates re-corridos en orden TODO VERDE: ruff check+format (83 files), pyright 0, pytest 534 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build. Total 645. Sin cambios de código; sin tests nuevos (§8) ni viejos tocados.
- Memoria rotada (22→archive verbatim + historial); `roadmap.md` ref→Sesión 23; `INDEX.md` honesto (download-throughput diferido); `observations.md` +2 abiertas; `graphify update .` + commit + push. Siguiente: Fase 16 Packaging.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
