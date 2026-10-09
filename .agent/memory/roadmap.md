# Roadmap — local-media-downloader

> Estado (✅/[ ]) + referencia. Detalle vive en lessons/session_log.
> La lista de fases se completa UNA vez durante el bootstrap, copiando los
> nombres/orden de fases desde IMPLEMENTATION_PLAN.md. Después de eso, solo
> se actualiza el estado (✅/[ ]) de cada fase — no se vuelve a copiar el
> plan completo.

## Fases

- [x] **Fase 0** — Repository foundation (monorepo, uv, pnpm, Svelte 5 + Vite + Tailwind, extension build, CI) — ver `session_log.md` Sesión 1
- [x] **Fase 1** — Local service skeleton (FastAPI + Granian, /api/v1/health con yt-dlp/yt-dlp-ejs/Deno/FFmpeg, config, logs) — ver `session_log.md` Sesión 1
- [x] **Fase 2** — SQLite + job state machine (WAL, schema, job events, transitions, recovery) — ver `session_log.md` Sesión 1
- [x] **Fase 3** — yt-dlp adapter (metadata, formato normalizado, error mapping, subprocess, yt-dlp-ejs/Deno, diagnóstico de versión) — ver `session_log.md` Sesión 4
- [x] **Fase 4** — FFmpeg/FFprobe adapters (inspection, remux, transcode, extracción audio, validación) — ver `session_log.md` Sesión 5
- [x] **Fase 5** — Execution planner (intent → ExecutionPlan, stream copy preferido, rechazar intents arbitrarios) — ver `session_log.md` Sesión 5
- [x] **Fase 6** — Scheduler + worker pool asyncio (3 jobs / 2 downloads / 1 encoder, cancelación, retries, backpressure, SSE de progreso) — ver `session_log.md` Sesión 6
- [x] **Fase 7** — Recovery and resilience (crash, power loss, disk full, network loss, FFmpeg crash) — ver `session_log.md` Sesión 7
- [x] **Fase 8** — Svelte 5 web UI (Dashboard, Resolve, Job details, History, Settings, Diagnostics; assets servidos por FastAPI) — ver `session_log.md` Sesión 8
- [x] **Fase 9** — Browser extension (popup, handoff URL, health indicator Connected/Offline, permisos activeTab+storage + host loopback) — ver `session_log.md` Sesión 9
- [x] **Fase 10** — Security hardening (loopback-only bind, token local, Origin/Host validation, allowlist de protocolo, límites de request, rate limit en resolve, output path + sanitización de filenames, redacción de secretos) — ver `session_log.md` Sesión 10
- [x] **Fase 11** — Native Messaging: **evaluada, NO se implementa** (veredicto en Sesión 11). El gate de `IMPLEMENTATION_PLAN.md` no puede cerrarse antes de Fase 16: el MVP localhost funciona, pero "instalación/distribución" solo se entiende cuando exista el paquete instalable. Se reevalúa en Fase 16.
- [x] **Fase 12** — Batch + history (multi-URL, historia paginada, retry manual, duplicados por URL normalizada+intent, prioridad reasignable, retention/cleanup, output root con reglas, notificaciones desktop vía dashboard, bandwidth reservado) — ver `session_log.md` Sesión 12
- [x] **Fase 13** — Media presets (Video, Audio, MP3, MP4, WebM, GIF, WebP, No audio, Mobile, WhatsApp sticker) — ver `session_log.md` Sesión 14
- [x] **Fase 14** — Advanced processing (trim, resize, crop, bitrate, framerate, codec h264/vp9/av1, loudnorm, subtítulos/metadata modelados y rechazados con UNSUPPORTED_INTENT + matriz §528) — ver `session_log.md` Sesión 21
- [x] **Fase 15** — Performance engineering (baselines verificados: startup, memoria, latencia API/cola, SQLite, disco, FFmpeg, UI; download-throughput diferido a red en vivo) — ver `session_log.md` Sesión 23
- [x] **Fase 16** — Packaging (Windows primero: PyInstaller onedir → Inno Setup, binarios bundled pineados, THIRD_PARTY_NOTICES) — ver `session_log.md` Sesión 25. Cierre con 2 reservas documentadas en `observations.md`; la del checklist browser real quedó **parcialmente resuelta** (el usuario probó la extensión en Thorium/Chromium con descargas reales de YouTube/Twitter/TikTok, sin fallos; resta Firefox y recorrer el resto de la UI), la del smoke del exe sigue abierta y necesita una máquina con más recursos.
- [x] **Fase 17** — Release hardening (reliability, seguridad, UX, compat Chromium/Firefox/Windows) — ver `session_log.md` Sesión 32. Cierre por verificación: todos los bullets ya cubiertos por tests existentes salvo cancel-running (nuevo `test_cancel_running_job` endurecido: CANCELLED estricto + no-orphans). De las 2 reservas de Fase 16 en `observations.md`, la del browser quedó parcialmente resuelta (Thorium/Chromium verificado; falta Firefox + resto de la UI) y la del smoke del bundle sigue abierta (requiere máquina con más recursos). Sesión 33 (post-MVP, sin fase nueva): bug de progreso en vivo (Regla 17.5) + detector de Diagnostics que mentía sobre Deno/EJS (Regla 17.6) + `yt-dlp-ejs` como dependencia real.

- **Post-MVP Sesión 34 — Rediseño visual completo (sin fase nueva):** sistema de tokens `@theme` + Archivo self-hosted + marca/íconos propios (web y extensión) + fondo con parallax GPU + cursores/focus globales + primitivas de carga (Spinner/Skeleton/Button busy/StateBadge) + stage rail con detección de congelamiento (staleness por etapa) + fixes reales de freshness (SSE en History, purga del store live, telemetría solo con datos). Serving de assets del dist root (Regla 17.8). Docs: `PRODUCT.md` + `DESIGN.md` + `.impeccable/design.json`. 705 tests. Ver `session_log.md` Sesión 34.

---

## Pendientes Críticos Detectados

- (ninguno abierto)

- **~~Deno no está instalado~~ (resuelto en Sesión 4):** Deno 2.9.6 vía pnpm devDependency raíz con `allowBuilds: { deno: true }` (pnpm 11 ignora `onlyBuiltDependencies`; corregido en Sesión 11 → Regla 10.3); se pasa a yt-dlp con `--js-runtimes deno:<path>`.
- **"Backend starts locally" de la acceptance de Fase 0 se difiere a Fase 1** por decisión explícita: Fase 0 no introduce FastAPI/Granian (el plan prohíbe deps antes de la fase que las requiere). `apps/api` queda como paquete importable + 1 test.
- **UX de la extensión verificada en Chromium, no en Firefox (actualizado 2026-10-08):** Fase 9 y Fase 10 están verificadas por tests (lógica pura, contratos, CLI), y además el usuario ejecutó el popup y el flujo `<meta>`/cookie/`EventSource` en **Thorium** (fork de Chromium) contra el servicio real, con descargas de YouTube/Twitter/TikTok y el preset "best available" funcionando y sin fallos. Queda sin ejecutar la rama Firefox del bridge (`apps/extension/src/browser/index.ts`), la confirmación directa del SSE autenticado por cookie, y el resto de la UI. El checklist concreto y su estado por ítem están en `observations.md`.
- **CI: filtro por paths (resuelto en Sesión 33, decisión del usuario).** `.github/workflows/ci.yml` disparaba los 4 jobs para cualquier push a `main`, incluso si solo tocaba `.agent/memory/` o `docs/`. Ahora `push` y `pull_request` llevan `paths-ignore: ['**.md', 'docs/**', '.agent/**']` (el run se saltea solo si TODOS los archivos tocados matchean; un commit que también toque código corre todo) y `workflow_dispatch` queda para correrlo a mano. Seguro porque `main` no tiene branch protection (verificado con la API: `Branch not protected`), o sea que no hay required checks que puedan quedar esperando.
