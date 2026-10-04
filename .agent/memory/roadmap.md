# Roadmap — local-media-downloader

> Estado (✅/[ ]) + referencia. Detalle vive en lessons/session_log.
> La lista de fases se completa UNA vez durante el bootstrap, copiando los
> nombres/orden de fases desde IMPLEMENTATION_PLAN.md. Después de eso, solo
> se actualiza el estado (✅/[ ]) de cada fase — no se vuelve a copiar el
> plan completo.

## Fases

- [x] **Fase 0** — Repository foundation (monorepo, uv, pnpm, Svelte 5 + Vite + Tailwind, extension build, CI) — ver `session_log.md` Sesión 1
- [x] **Fase 1** — Local service skeleton (FastAPI + Granian, /api/v1/health con yt-dlp/yt-dlp-ejs/Deno/FFmpeg, config, logs) — ver `session_log.md` Sesión 1
- [ ] **Fase 2** — SQLite + job state machine (WAL, schema, job events, transitions, recovery)
- [ ] **Fase 3** — yt-dlp adapter (metadata, formato normalizado, error mapping, subprocess, yt-dlp-ejs/Deno, diagnóstico de versión)
- [ ] **Fase 4** — FFmpeg/FFprobe adapters (inspection, remux, transcode, extracción audio, validación)
- [ ] **Fase 5** — Execution planner (intent → ExecutionPlan, stream copy preferido, rechazar intents arbitrarios)
- [ ] **Fase 6** — Scheduler + worker pool asyncio (3 jobs / 2 downloads / 1 encoder, cancelación, retries, backpressure, SSE de progreso)
- [ ] **Fase 7** — Recovery and resilience (crash, power loss, disk full, network loss, FFmpeg crash)
- [ ] **Fase 8** — Svelte 5 web UI (Dashboard, Resolve, Job details, History, Settings, Diagnostics; assets servidos por FastAPI)
- [ ] **Fase 9** — Browser extension (popup, handoff URL, health indicator Connected/Offline, permisos mínimos activeTab+storage)
- [ ] **Fase 10** — Security hardening (loopback, token local, Origin validation, protocol allowlist, sanitización)
- [ ] **Fase 11** — Native Messaging (evaluar gate: solo si localhost MVP y UX validados)
- [ ] **Fase 12** — Batch + history (multi-URL, historia, retry, duplicados, cleanup)
- [ ] **Fase 13** — Media presets (Video, Audio, MP3, MP4, WebM, GIF, WebP, No audio, Mobile, WhatsApp sticker)
- [ ] **Fase 14** — Advanced processing (trim, crop, resize, bitrate, framerate, subtítulos, metadata)
- [ ] **Fase 15** — Performance engineering (medir startup, memoria, CPU, throughput, latencia)
- [ ] **Fase 16** — Packaging (Windows primero: PyInstaller onedir → Inno Setup, binarios bundled pineados, THIRD_PARTY_NOTICES)
- [ ] **Fase 17** — Release hardening (reliability, seguridad, UX, compat Chromium/Firefox/Windows)

---

## Pendientes Críticos Detectados

- **Deno no está instalado** en la máquina (Fase 3 lo necesita como runtime JS de yt-dlp-ejs). Instalar antes de la Fase 3.
- **"Backend starts locally" de la acceptance de Fase 0 se difiere a Fase 1** por decisión explícita: Fase 0 no introduce FastAPI/Granian (el plan prohíbe deps antes de la fase que las requiere). `apps/api` queda como paquete importable + 1 test.
- **`docs/`, `.agent/`, `CLAUDE.md` siguen sin trackear en git** (el "Initial commit" sólo llevaba `.gitignore` + `README.md`). Hay que decidir si se commitean antes del primer release. `.claude/`, `.opencode/` y `graphify-out/` ya están en `.gitignore` a propósito.
