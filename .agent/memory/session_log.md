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

`Sesión 4 — 2026-10-04 — space-bunny-free vía OpenCode (PowerShell/Windows)`

### Fase 3 — yt-dlp adapter: completada

**Dependencias:** `yt-dlp==2026.8.19` vía `uv add` (dependencia Python; se invoca como
`[sys.executable, "-m", "yt_dlp"]`, nunca del PATH). **Deno 2.9.6 vía pnpm** como
devDependency raíz: su binario se descarga en postinstall, así que hizo falta
`onlyBuiltDependencies: [deno]` en `pnpm-workspace.yaml` — en pnpm 11 esa setting ya NO
se lee del campo `pnpm` de package.json (warning explícito). Se le pasa a yt-dlp con
`--js-runtimes deno:<path>`, no por variable de entorno.

**Estructura nueva (capas, principio #3):**
- `domain/errors.py` — `ErrorCode` (16 categorías) + `ExtractionError` con flag
  `retryable` y `detail` sólo para diagnóstico.
- `domain/media.py` — `MediaFormat`, `MediaSource`, `MediaInfo`, `FormatKind`.
- `domain/extractor.py` — `Protocol Extractor` (adapters reemplazables, #24).
- `domain/urls.py` — allowlist http/https; rechaza `file:`, `javascript:`, `data:`, etc.
- `adapters/tool_paths.py` — orden override → `node_modules/.bin` → venv → PATH.
- `adapters/errors.py` — tabla de mapeo stderr de yt-dlp → `ErrorCode`, como datos.
- `adapters/normalize.py` — el único lugar que conoce el schema de yt-dlp.
- `adapters/progress.py` — parseo de `--progress-template` con delimitador privado.
- `adapters/yt_dlp.py` — `YtDlpExtractor` (version/resolve/download), argv arrays.
- `services/resolve.py` — `ResolveService` + `error_response` con status por código.
- API: `POST /api/v1/resolve`, y `/api/v1/health` ahora incluye `extractor` con la
  versión y el flag `may_be_outdated`. `create_app` acepta `extractor_factory` para que
  los tests no lanzen el network.

**Cuatro decisiones de diseño que cambiaron código, no tests:**
1. **`quality_score` estaba mal.** Daba 400 puntos a "combined", así que un 360p muxed
   (489) le ganaba a un 1080p video-only (314) — exactamente el "fake maximum quality"
   del principio #6. Reescrito: la resolución domina y "combined" sólo desempata.
2. **La validación de URL vivía en el adapter**, así que un extractor stub la
   esquivaba y `file:///C:/...` devolvía 200. Movida al service (frontera), mantenida
   también en el adapter.
3. **Links directos a media devolvían 0 formatos.** El extractor `generic` reporta
   `vcodec/acodec: unknown` y el filtro los descartaba. Ahora se clasifica por
   contenedor (`_VIDEO_CONTAINERS`) y se emite un warning que obliga a confirmar con
   FFprobe antes de afirmar capacidades (principio #17).
4. **Ordering del mapeo de errores:** `HTTP Error 429` caía en el patrón genérico de
   4xx y se reportaba `SOURCE_UNAVAILABLE` en vez de `RATE_LIMITED`. `429` quedó
   excluido del patrón genérico y la regla de rate limit se evalúa antes. Además
   `available in your country` (no `not available in your country`) es lo que yt-dlp
   emite de verdad.

**Tests: 128 unitarios + 3 live opt-in** (`LMD_LIVE_NETWORK=1`; los live nunca corren
en CI). Cubren normalización contra un fixture JSON real, la tabla de mapeo de errores
de forma exhaustiva, el parseo de progress (incluido que NUNCA parsea la línea humana),
la política de URLs, el contrato del endpoint con extractor stub, y que la versión
reportada sea la pineada en `uv.lock` (`yt-dlp --version` da `2026.08.19` con zero
padding, la metadata da `2026.8.19`, así que se compara numéricamente).

**Acceptance verificada en vivo** contra
`archive.org/.../big_buck_bunny_720p_surround.mp4`: resuelve a `MediaInfo` con
extractor `generic`, 1 formato `video`, `duration: None` (no se sondea un link directo:
null, no valor inventado), y sin ninguna clave del schema de yt-dlp en la respuesta.
Los 3 tests live pasan. El bug del punto 3 se detectó justamente con esta corrida.

**Gates:** ruff + format clean, pyright 0, pytest 128/128, y del lado JS eslint,
prettier, svelte-check+tsc, vitest, ambos builds. Prettier detectó `pnpm-workspace.yaml`
sin formatear y lo corregí antes de commitear.

### Chequeo final PROTOCOLO_SALIDA

- [x] 1 sola sesión en detalle (Sesión 4). Sesiones 1-3 comprimidas en historial con
      detalle verbatim en `session_log_archive.md`.
- [x] Sin duplicación Regla↔tech_stack: la narrativa vive sólo en
      `lessons_learned.md`; `tech_stack.md` referencia por número.
- [x] Loose ends de la sesión: ninguno.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine. `job_state.py`,
  `migrations.py`, `db.py` (WAL + `BEGIN IMMEDIATE`), `jobs.py`; lifespan en `app.py`.
  37 tests; recovery de un job DOWNLOADING tras "muerte" del proceso verificado en vivo.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian. `config.py`,
  `logging_config.py`, `diagnostics.py`, `app.py`, `__main__.py`; health con detección de
  5 tools; entry point `lmd-api`. 8 tests. Verificado en vivo en 127.0.0.1:8765.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm con `apps/api`, `apps/web`,
  `apps/extension`, `packages/contracts`; ESLint+Prettier; CI en windows+ubuntu;
  `.gitignore` saneado y hooks `pre-commit`. 12 tests. Reglas de Oro 1.1, 1.2, 1.3.