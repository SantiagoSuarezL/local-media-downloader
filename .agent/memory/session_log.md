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

`Sesión 32 — 2026-10-08 — opencode/muse-spark (TikTok curl-cffi + Ctrl+C hang) vía OpenCode`

- TikTok 502 `EXTRACTION_FAILED`: forensic `yt-dlp -v` mostró "attempting impersonation, but no impersonate target is available" → TikTok rechaza el TLS vanilla de Python. Sin dependencia `curl_cffi` TODO TikTok fallaba. Con curl-cffi: impersonación OK (`chrome-150`); el video de muestra queda "Your IP address is blocked" (error esperado del servidor, clasificado ahora como SOURCE_UNAVAILABLE retryable).
- Fix: `curl-cffi>=0.13` en deps (lock 0.16.3) + mapeo `ip address` en `_UNAVAILABLE` + test de regresión + THIRD_PARTY_NOTICES + `lmd.spec` con `collect_all("curl_cffi")` (data+binaries+hiddens) para el bundle. NOTA: el `uv sync` no pudo correr (backend del usuario mantenía el venv lockeado) → usuario debe `uv sync` al reiniciar.
- Ctrl+C hang (usuario: tras "Stopping worker-1" no devuelve la terminal): `_event_stream` espera `queue.get()` para siempre y Granian tenía `workers_kill_timeout` disabled (default None) → el SSE abierto del dashboard impedía que el worker termine. Fix: `workers_kill_timeout=1` en `__main__.py` (kill duro a 1 s del grace). Mi simulación por pipes no reproduce la consola real (Ctrl+C en Windows es un evento de consola, no una señal a un pipe) — la verificación definitiva es el Ctrl+C del usuario sobre el backend real.
- Gates: ruff/pyright, pytest 547 fast + smoke 1, prettier OK. Total 661. Regla 17.4.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 31 — 2026-10-08` — Probe del popup a 6 s (cache-miss lento de health: 4 subprocess secuenciales); frontend verde.
- `Sesión 30 — 2026-10-08` — Popup Offline intermitente (cache-miss vs timeout): retry ante throw + detalle preservado; 3 tests; frontend verde.
- `Sesión 29 — 2026-10-08` — Saga sticker-webp interop (ANMF sub-frames vs decoder ≤8.x) + CI 4/4 con BtbN 9.0 en ambos OS; 657 tests, Regla 17.3.
- `Sesión 28 — 2026-10-08` — FFmpeg en CI ubuntu + fix 403 dev (`changeOrigin: true`, Regla 17.2); frontend verde.
- `Sesión 27 — 2026-10-08` — Trial browser (servidor WMI desacoplado, health+shell OK) + CI ubuntu en verde (glibc vs Winsock, Regla 17.1); 655 tests.
- `Sesión 26 — 2026-10-08` — Revisión HANDOFF + cierre Fase 17: test cancel-running endurecido (CANCELLED estricto + no-orphans); gates verdes, 653 tests.
- `Sesión 25 — 2026-10-08` — Cierre Fase 16 con 2 reservas de hardware (smoke bundle + browser real, en observations.md); sin código; gates dev verdes Sesión 24.
- `Sesión 24 — 2026-10-08` — Revisión HANDOFF Fase 16: spec portable, web_dist/bin frozen-aware, entry shim, staging script; bundle compila 2× pero smoke colgado → Fase 16 abierta; 652 tests verdes.
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
