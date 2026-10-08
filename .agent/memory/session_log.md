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

`Sesión 25 — 2026-10-08 — opencode/muse-spark (cierre Fase 16 con reservas de hardware) vía OpenCode`

- Procesos: 24 `python.exe` del Python del sistema (`AppData\Programs\Python312`, NO del `.venv` del proyecto), todos hijos `multiprocessing.spawn` huérfanos (0/24 padres vivos), 4–15 MB c/u. No son del proyecto → no se tocan. Sin restos del bundle (exe/ffmpeg limpio). `dist/`+`build/` eliminados (gitignored).
- Cierre Fase 16 con 2 reservas documentadas (la laptop no aguanta el smoke del bundle: 2 intentos caídos por recursos): (1) smoke del exe frozen — compilación probada 3× OK, boot real pendiente en máquina con resto/CI; (2) checklist browser real (Chrome/Firefox) — requiere humano, 5 minutos. Cómo re-verificar: `pnpm build` + pyinstaller con spec + `stage_bundle.ps1` + boot con `LMD_DATA_DIR` temporal (comandos en observations.md). Sin cambios de código en esta sesión; gates dev ya verdes sobre el mismo árbol (Sesión 24).
- `uv run --package local-media-downloader-api --extra build` desde repo root: compila sin podar dev deps (lección Sesión 24).
- Memoria rotada (24→archive verbatim + historial); `roadmap.md` Fase 16 ✅ con reservas; `graphify update .` + commit + push. Siguiente: Fase 17 Release hardening (y las 2 reservas cuando haya máquina/restos).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
