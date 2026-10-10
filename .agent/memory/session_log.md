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

`Sesión 36 — 2026-10-10 — opencode/muse-spark vía OpenCode (PowerShell/Windows)`

- **Pipeline de release** (el "paso natural" para no-técnicos): nuevo `.github/workflows/release.yml` — tag `v*` publica GitHub Release, dispatch manual solo sube artefactos. Job en windows-latest: pnpm build, FFmpeg BtbN 9.x pineado, PyInstaller onedir (receta de observations), stage_bundle, **smoke del bundle** (boot real + banner + shell con token, kill por CommandLine), Inno con versión del tag (`/DMyAppVersion`), zip de `apps/extension/dist`, publish con `gh release create --generate-notes`.
- **Fix bloqueante de release:** `config.default_data_dir()` — el frozen defaultea a `%APPDATA%\Local Media Downloader` (la misma carpeta que el .iss crea/limpia) en vez de `data/` junto al exe (Program Files sin escritura); `LMD_DATA_DIR` sigue ganando. +2 tests en `test_config.py` (frozen default + override).
- **`installer.iss`:** versión por `/D` con fallback 0.1.0, URLs reales del repo (estaban en `example/`), icono de escritorio marcado por defecto.
- **README:** sección "Install from a release" (instalador + zip + extensión unpacked, sin toolchain; Web Store fuera de alcance por el fee de desarrollador).
- **Gates:** pytest config+app 27 passed, ruff/pyright 0, prettier ok, YAML del workflow parseado. El smoke real del bundle queda en manos del primer run del workflow (reserva Fase 16: atacada, no cerrada hasta verlo verde en CI).
- **Post-fix del primer run rojo (mismo día):** el smoke en CI falló con `frozen bundle never served its banner` → causa raíz: Granian spawnea el worker con multiprocessing aunque `workers=1` (`MPServer`, `BUILD_GIL True` en 3.12) y el exe frozen re-ejecuta `sys.executable` como hijo — sin `freeze_support()` en `lmd_entry.py` el "worker" arrancaba otro servidor. **Regla 17.10.** Fix + smoke del workflow ahora con fail-fast (`HasExited`) y captura/dump de stdout/stderr del exe. Verificado LOCAL de punta a punta (build frozen ~46 s → banner instantáneo → shell con token → árbol exe+1 worker → kill limpio, artefactos borrados ~600 MB) y **en CI: run 38067647416 success completo** — la reserva de smoke de Fase 16 queda CERRADA (observación archivada).
- **Publicación de v0.1.0 (mismo día):** el primer push del tag falló en el job `publish` — `gh release create` sin checkout no puede detectar el repo (`failed to run git: fatal: not a git repository`, run 38077832131; el build del tag sí quedó verde). Fix: `--repo ${{ github.repository }}` explícito. **Regla 17.11.** Como el run de un tag usa el workflow del commit del tag, el tag se movió al commit del fix (sin release creado, borrar y re-tagear es limpio).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 35 — 2026-10-10` — Fix fantasma post-completed (ingest ignora scheduler, JobDetails revalida + resync 409, 121 Vitest) + launcher doble clic Start-LMD.bat/.ps1 verificado con boot real + README daily use.

- `Sesión 34 — 2026-10-08` — Rediseño visual completo + branding app y extensión (DESIGN.md normativo, Archivo self-hosted, íconos propios, stage rail con staleness, fix SSE en History + serving dist-root, Reglas 17.8/17.9). 705 tests.

- `Sesión 33 — 2026-10-08` — Progreso en vivo (17.5) + Diagnostics resuelve binarios como el adapter (17.6) + `yt-dlp-ejs` como dependencia real; push con fix CI/Deno (17.7). 675 tests.

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
