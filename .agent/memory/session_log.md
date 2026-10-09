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

`Sesión 34 — 2026-10-08 — opencode/kimi-k3 (rediseño visual completo + branding de app y extensión) vía OpenCode`

- **Flujo de diseño con impeccable:** `PRODUCT.md` (verdad de producto, raíz) → `concept-seed --mode operate` (asignada "transfer bay": grafito + seams de 1px en vez de sombras + sky solo para "está pasando ahora") → surface brief con Direction contract en `apps/web/.impeccable/surfaces/` → build code-led. Decisiones del usuario: sky manda (bolt violeta del favicon recoloreado a sky), Archivo self-hosted (no CDN — local-first), fila de History clickeable completa, todo en una sesión con gates al final.
- **Sistema de diseño:** `app.css` pasó de 1 línea a tokens `@theme` (19 colores nombrados + Archivo + mono) + utilidad `.fig` (tabular-nums para números en movimiento). Archivo woff2 self-hosted (latin + latin-ext, ~67 KB, `tnum` verificado con fonttools, preload en el shell, SIL OFL en THIRD_PARTY_NOTICES). `class="dark"` inerte → `color-scheme: dark` (scrollbars/controles nativos oscuros reales). Favicon reescrito 9.5 KB → 975 B (mismo bolt, sky) + `Mark.svelte` + set de 18 íconos propios (`icons/paths.ts` + `Icon.svelte`, stroke 1.5, currentColor, sin librería). Fondo: glow radial + grilla de seams 48px con parallax `translate3d` en listener pasivo coalescido a rAF (desactivado bajo prefers-reduced-motion); header sticky sólido (sin backdrop-blur: cuesta un frame por scroll).
- **El "punto 4" era un bug de datos, no de estética:** History **nunca escuchaba el SSE** (tabla congelada mientras el Dashboard seguía moviéndose) y el store `live` nunca purgaba entradas. Fix: `LiveJob.updatedAt`, purga terminal a 5 s, `clock` compartido que solo tica con trabajo en vuelo, `jobState.ts` nuevo (`railFor/stageIndex/toneFor/railSummary/railVisible` + presupuestos de staleness por etapa 15s/90s/45s/20s — 90 s para FFmpeg a propósito). Primitivas Spinner/Skeleton/Button(busy, aria-busy, label estable)/StateBadge(lámpara+palabra)/StageRail. Feedback del usuario: el rail leía "barra fantasma" en completados → solo se dibuja cuando hay etapa en juego (`railVisible`); Job details: telemetría sin dato ya no renderiza placeholders `—` permanentes (el registro durable nunca persistió bytes — observación nueva abierta).
- **Bug de serving encontrado en verificación end-to-end:** todo asset del dist root (`favicon.svg`, `fonts/*.woff2`) caía al fallback SPA y llegaba como `text/html` (la fuente "no funcionaba" sin error visible). Fix en `app.py::_mount_web_ui`: el catch-all sirve archivos reales con `FileResponse` + content-type explícito (`index.html` siempre por la vía del token, traversal bloqueado) + test de regresión (content-type + bytes exactos + token en `/index.html`). Regla 17.8. Además, verificar servidores reales en Windows: el wrapper `uv` deja python huérfano y dos generaciones double-bindearon :8791 por SO_REUSEADDR (mi curl leía el proceso viejo). Regla 17.9. Nota: lightningcss dropea `scrollbar-color/width` declarados junto a `::-webkit-*` en el mismo bloque ("Invalid token" silencioso) → solo quedó webkit, comentario en app.css.
- **Extensión:** íconos MV3 (16/32/48/128, bolt sky sobre tile; 128 desde captura 256 porque Chrome headless renderiza 128 vacío en esta clase de máquina — Edge headless policy-locked; receta dentro de `public/icons/icon.svg`), manifest + test de contrato (tamaños + archivos existen en `public/`), popup re-estilizado a los tokens (el detector lo marcó: 13 findings, incluyendo contraste 4.2:1 en labels → ahora 7.6:1; detector final 0 findings). Docs del sistema: `PRODUCT.md` + `DESIGN.md` + `.impeccable/design.json` (spec Stitch, ramps tonales generadas por script), en raíz porque el tooling los busca ahí; listados en README. Gates finales: ruff/pyright 0, pytest 563, Vitest 116 web + 26 extensión, builds limpios.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

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
