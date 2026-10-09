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

`Sesión 33 — 2026-10-08 — opencode/space-bunny-free (fixes de reporte del usuario) vía OpenCode`

- El usuario preguntó por Settings/Diagnostics/priority y reportó que Downloaded/Speed/ETA salían siempre `—`. Forensics contra la herramienta real (servidor HTTP local + el `TEMPLATE` del repo): la línea `download:lmd\x1f...` nunca se imprime — `download:` es la CLAVE del tipo de salida de `--progress-template` y yt-dlp la consume, así que toda línea se descartaba en silencio (el parser era correcto). Fix: template sin prefijo de tipo ni `\n` final, `RECORD_PREFIX` en el parser, y el test nuevo produce la línea con `parse_options` + `YoutubeDL.evaluate_outtmpl` (0 registros antes, 15 después con bytes/velocidad). Regla 17.5.
- `detect_tools` probaba `deno`/`ffmpeg`/etc. por PATH mientras el runtime usa `tool_paths` → Diagnostics reportaba `deno: no` con Deno corriendo desde `node_modules/.bin`. Fix: los probes componen argv con `yt_dlp_argv()`/`find_deno()`/`ffmpeg_argv()`/`ffprobe_argv()` (y `_ejs_version()` acepta `version`/`__version__`), sigue reportando solo la primera línea para no filtrar paths. Nuevo `tests/test_diagnostics.py` (11 tests). Regla 17.6.
- Gap de spec: `TECHNICAL_SPEC` §exige `yt-dlp-ejs` desde la Fase 1 pero nunca estuvo en `pyproject.toml` (`tech_stack.md` lo declaraba, el venv no lo tenía). Agregado `yt-dlp-ejs>=0.3.2` (lock 0.8.0) + `collect_all`/hiddenimport en `lmd.spec` + THIRD_PARTY_NOTICES; además corregí la licencia de yt-dlp en el notice (es The Unlicense, no "GPL v3" — verificado en el metadata del dist-info).
- Gates: ruff/pyright 0, pytest 561 fast + smoke 1, prettier/eslint/svelte-check, 88+25 Vitest. Total 675. Reglas 17.5 y 17.6 agregadas; 14.1/14.2 archivadas por rotación.
- CI: el usuario preguntó por qué corría en cada commit → `paths-ignore: ['**.md', 'docs/**', '.agent/**']` en `push` y `pull_request` (con comentario que nombra la regla: nada del build lee `.md`; los tests de packaging leen `pyproject.toml`/`lmd.spec`). Verificado: YAML parsea, prettier limpio, `main` sin branch protection (sin required checks que puedan quedar esperando).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 32 — 2026-10-08` — TikTok con curl-cffi (impersonation) + `workers_kill_timeout=1` (Ctrl+C hang); README user-facing; commit `2f251ca`.

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
