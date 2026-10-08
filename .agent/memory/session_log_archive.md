# Session Log — ARCHIVO — local-media-downloader

> Detalle completo verbatim de sesiones pasadas. No se lee automático.
> Consultar solo si hace falta el detalle exacto de archivos/tests/decisiones
> de una fase vieja.

## Archivo de sesiones

### Sesión 13 — 2026-10-07 — opencode/muse-spark vía OpenCode (PowerShell/Windows)

- Sistema de gates para modelos baratos: nuevo `docs/TESTING.md` (orden de gates, política STOP con HANDOFF, matriz fases 13-17, pitfalls); regla 11 en IMPLEMENTATION_PLAN; §24 de TECHNICAL_SPEC apunta a TESTING.md; README suma el puntero. Sin commit todavía.
- **Backend:** `tests/test_contracts.py` (13 tests: todo ErrorCode con status explícito, key sets exactos de cada DTO, envelope único de errores; fixture con NoopExecutor para que el scheduler no toque red) + `tests/test_smoke_e2e.py` (`-m smoke`: servidor real Granian en puerto fresco + data dir temporal, handoff de token por shell/cookie, matriz de status, batch por-ítem, persistencia tras reinicio con mismo token); marker `smoke` registrado en pyproject. Hallazgo: la sonda 413 envenena el keep-alive (va última, con cliente fresco).
- **Frontend:** suite Vitest nueva en `apps/web` (85 tests: `format/presets/api/live/notify`, Zod `.strict()` en `tests/schemas.ts` — devDependency, no va al bundle — y componentes `JobCard`/`Batch`); `test` script + `resolve.conditions: ['browser']` en vite.config (sin eso `mount()` falla con lifecycle_function_unavailable); `tests/**` entra a tsconfig.app para svelte-check. `pnpm -r test` ya la incluye en CI sin cambios.
- **Gates:** pytest 308 passed/3 skipped, pyright 0, ruff check+format clean, pnpm lint/format:check/check/test/build verdes (22 vitest ext + 85 web). Total: 415 tests (412 run + 3 live opt-in).
- Observación nueva en `observations.md`: batch de 100 URLs largas (~225 KB) superaría el límite 64 KiB → 413 legítimo pero extremo; monitorear cuando crezcan los intents (Fase 13/14).

### Sesión 12 — 2026-10-07 — opencode/muse-spark vía OpenCode (PowerShell/Windows)

- Fase 12 (Batch + history) implementada completa, backend + web. Sin commit todavía (pendiente decisión del usuario).
- **Dominio nuevo:** `domain/urls.py::normalize_url` (lowercase scheme/host, sin puerto default, sin fragment, sin tracking params, query ordenada); `domain/dedupe.py` (`intent_fingerprint` con JSON canonical + `dedupe_key = sha256(url_norm + intent)`); `domain/output.py` (reglas cerradas `flat`/`by_extractor`/`by_date`, sanitización por segmento, prueba de contención).
- **Schema v3:** columna `dedupe_key` + `idx_jobs_dedupe` + `idx_jobs_updated_at`; test de upgrade v2→v3 en `test_db.py` (filas viejas leen con key NULL y nunca matchean).
- **Repositorio (`jobs.py`):** `create_job` acepta `dedupe_key`; `find_duplicate` (misma key + estado no-terminal; COMPLETED/FAILED/CANCELLED no cuentan); `clear_source_url` (NO toca `updated_at` → Regla 12.1); `delete_job`; `list_terminal_older_than`; `set_priority`; `reset_for_retry` (resetea intentos+errores, devuelve el job).
- **State machine:** `CANCELLED → RETRY_WAIT` agregado (retry manual de cancelados accidentales; COMPLETED sigue terminal).
- **Servicios:** `services/retention.py` (3 relojes sobre `updated_at`: `source_url_retention`, `temporary_retention_hours`, `history_retention_days`; sweep al startup + cada 6 h + endpoint manual; nunca crashea el sweep); `services/batch.py` (async, por-item: intent → rate limit → resolve en thread → plan → dedupe → create; publica `batch_submitted`). Notificaciones: sin servicio nuevo — el dashboard usa los eventos SSE existentes + Notification API (opt-in, `lib/notify.ts`).
- **API:** `POST /jobs/batch` (1–100 items, resultados por índice), dedupe también en `POST /jobs` single (200 + `"duplicate": true`, resolve pasa a `asyncio.to_thread`), `POST /jobs/{id}/retry` (FAILED/CANCELLED/RECOVERY_REQUIRED; 409 si URL redactada), `POST /jobs/{id}/priority` (±100), `GET /jobs` con `limit/cursor/states` + `next_cursor` (cursor base64url; `response_model=None` → Regla 12.2), `POST /maintenance/cleanup`, `PATCH /settings` (solo claves runtime, `extra="forbid"`).
- **Executor:** el output final va a `output_root` con la regla configurada (`LMD_OUTPUT_ROOT`, default `~/Downloads/Local Media Downloader`; `LMD_OUTPUT_RULE`); `data_dir/output` como fallback en tests. `bandwidth_limit_bps` solo reservado (reportado, no enforceado).
- **Web:** pantalla Batch (textarea multi-URL + preset + prioridad + tabla de resultados), History con paginación/Load more + Retry por fila + Run cleanup, JobDetails con Retry + editor de prioridad, Settings con sección editable de retention/output + toggle de notificaciones; `lib/presets.ts` compartido (Resolve refactorizado a usarlo).
- **Gates:** pytest 294 passed/3 skipped, pyright 0, ruff check+format clean, pnpm lint/format:check/check/test/build verdes (22 vitest). Reglas nuevas 12.1, 12.2; 9.1 archivada por rotación.

### Sesión 10 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)

- Fase 10 (Security hardening) — nuevo `security.py`: token de instalación persistido en la tabla `settings` (`secrets.token_urlsafe`, comparación con `compare_digest`, registrado como secreto para redacción), validación de `Host`/`Origin` strictly-loopback (anti DNS-rebinding), y `assert_loopback_host` que aborta el arranque con `LMD_HOST=0.0.0.0` (verificado e2e).
- Middleware `security_boundary` en `app.py`: Host/Origin → 403, `Content-Length` > 64 KiB (`LMD_MAX_REQUEST_BYTES`) → 413, y token obligatorio en todo `/api/*` salvo `/api/v1` y `/api/v1/health` (públicos porque la extensión solo puede hacer health). El token llega al dashboard por `<meta name="lmd-token">` + cookie `HttpOnly`/`SameSite=Strict` inyectados en el shell (ya validado contra Host), y la SPA lo manda por header; el SSE se autentica con la cookie porque EventSource no setea headers.
- `domain/urls.py`: se rechazan credenciales embebidas (`user:pass@`) y hosts loopback/privados/link-local/metadata (`127.0.0.1`, `localhost`, `192.168.*`, `169.254.169.254`, `.local`, `[::1]`) con el nuevo `ErrorCode.BLOCKED_SOURCE` → **se revierte** la decisión de Fase 1 de permitir loopback como origen, porque convertía la app en proxy SSRF a la LAN.
- `domain/filenames.py`: `sanitize_filename` (strip de separadores/caracteres Windows, reservados `CON`/`COM1`…, NUL, trim, tope 120 chars) + `output_path_for` que **prueba** contención en el output dir del job; el executor ya no arma la ruta con el título crudo.
- `services/rate_limit.py` (token bucket) aplicado a `POST /api/v1/resolve` (30/min, `LMD_RESOLVE_RATE_LIMIT`) con `Retry-After`; el health público cachea 5 s porque su detección de tools lanza subprocesses (DoS local).
- `logging_config`: `register_secret` + redacción de secretos en mensaje y extras.
- Bugs encontrados: (1) `_STATUS_BY_CODE` sin `UNSUPPORTED_INTENT`/`VALIDATION_FAILED`/`BLOCKED_SOURCE` devolvía 500 a errores del usuario (Regla 10.1); (2) bug propio: `_host_of` recibía `//host` y le anteponía otro esquema → todos los requests 403 (caído por tests); (3) `Origin: null` se aceptaba y ahora se rechaza; (4) `asyncio.run()` sobre un `asyncio.Lock` creado en el lifespan → el endpoint resolve pasó a `async` con `asyncio.to_thread` para el subprocess.
- `tests/conftest.py` con `serving()`: los tests usan `Host` loopback y token real, igual que el dashboard. `test_security.py`: 53 tests (bind, DNS rebinding, cross-origin, token/cookie/persistencia, no-log del token, 413, 422 URL larga, rate limit 429, `file://`/`../../`/`data:`/`javascript:`/`127.0.0.1`/comandos, filenames + contención, `shell=True` ausente).
- Gates: pytest 246 passed / 3 live skipped, pyright 0, ruff clean, svelte-check 0, eslint+prettier clean, vitest 22, builds web+extension ok. E2E verificado contra servidor real en `:8766` (el `:8765` quedó tomado por un worker huérfano de la Sesión 8 → Regla 10.2).
- Commit `8666100` (fases 7–10) pusheado a main; `gh` CLI instalado vía scoop (2.102.0) y CI consultado por la API pública de GitHub: **`frontend` venía en rojo desde el commit de Fase 3** mientras `backend` pasaba en ambos OS. Causa: pnpm 11 remueve `onlyBuiltDependencies` (ignorada en silencio) y el install limpio moría con `ERR_PNPM_IGNORED_BUILDS` (deno nunca corría su postinstall → tampoco estaba el runtime JS de yt-dlp-ejs). Fix: `allowBuilds: { deno: true }`, verificado en un clon limpio con los 5 pasos del job frontend (Regla 10.3).

### Sesión 9 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)

- Fase 9 (Browser extension MV3): popup con URL de la pestaña actual, botón "Open in Local Media Downloader", campo "Paste URL", indicador Connected/Offline y editor de dirección del servicio (guardada con `storage.local`, default `http://127.0.0.1:8765`). El botón de handoff queda deshabilitado si el servicio no responde (evita abrir una pestaña a la página de error del browser).
- `src/lib/handoff.ts` (lógica pura, testeada): `normalizeServiceUrl` acepta SOLO loopback http(s) y devuelve el origin; `validateMediaUrl` rechaza `chrome://`, `file://`, `javascript:`, `data:`, `about:` y URLs >2048 con un motivo legible; `buildDashboardUrl` manda la URL como `?url=<encodeURIComponent>`.
- `src/service/client.ts`: `checkHealth()` con `AbortController` (timeout 1500 ms) → `connected`/`offline` + detalle; nunca propaga excepción (servidor caído es un estado esperado) y una `degraded` se reporta como conectada pero degradada.
- `BrowserBridge` gana `storage()` (chrome.storage.local / browser.storage.local) para que el popup guarde la dirección del servicio; manifest suma `host_permissions` SOLO loopback.
- Handoff en la web: `App.svelte` lee `?url=` y abre la pestaña Resolve con el campo prellenado (sin router).
- Tests: 18 nuevos vitest (`handoff.test.ts` 9, `client.test.ts` 6, `manifest.test.ts` 3) — 22 vitest en total. Gates: pytest 186 passed/3 skipped, pyright 0, ruff clean, tsc+svelte-check 0, eslint+prettier clean, builds web+extension ok.

### Sesión 8 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)

- Fase 8 (Svelte 5 web UI): 6 pantallas (Dashboard con progreso SSE en vivo vía store compartido `live.ts`, Resolve con metadata+formatos+8 presets, Job details, History con filtros, Settings read-only, Diagnostics); tipos compartidos en `packages/contracts`; proxy dev `/api` → 127.0.0.1:`LMD_PORT`.
- Backend: `GET /api/v1/settings` (read-only); FastAPI sirve `apps/web/dist` en `/` (`_mount_web_ui`: `/assets` estáticos + fallback SPA; `/api/*` desconocido sigue 404 JSON); banner `GET /` movido a `GET /api/v1` (la `/` es del SPA); `created_at/updated_at` agregadas a `_job_dict`.
- Bugs encontrados y resueltos: (1) `.gitignore` heredado ignoraba `apps/web/src/lib/` (patrón `lib/`) — código fuente invisible a git; anclados a raíz los patrones de dirs de plantilla (`lib/`, `build/`, `var/`, `target/`, `dist/`, `tmp/`, `temp/`, `cover/`, `coverage/`, etc.) → Regla 8.1, observación `.gitignore` cerrada. (2) SPA fallback tragaba `/api/v1/*` desconocidos (200 HTML) → excluidos, 404 JSON. (3) JobCard ocultaba Cancel en QUEUED aunque la API lo soporta. (4) ESLint no parseaba TS en `.svelte` (faltaba `parserOptions.parser`) → fix en `eslint.config.js`.
- Tests: `test_app.py` +2 (settings, static mount con dist temporal; fixture hermética con `LMD_WEB_DIST` a dir inexistente); gates verdes: pytest 186 passed/3 skipped, pyright 0, ruff clean, svelte-check 0, eslint+prettier clean, `pnpm build` (web+extension) ok, vitest 4 passed. Verificado e2e con build real: `/` sirve el shell, `/api/v1/nope` 404 JSON.
- `graphify update` corrido.

### Sesión 7 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)

- Fase 7 (Recovery and resilience): nuevo `apps/api/src/local_media_downloader/services/recovery.py` con `recover_interrupted_jobs()` — corre en el lifespan antes de `scheduler.start()`; reconcilia estados vivos huérfanos (crash/power-loss): recola QUEUED (limpio de partials en `source/`/`work/`), `COMMITTING` ambiguo → `RECOVERY_REQUIRED` (nunca borra output posiblemente final), budget de attempts agotado → `FAILED` con `error_code=INTERRUPTED`, sin plan → `RECOVERY_REQUIRED`, `CANCEL_REQUESTED` con worker muerto → `CANCELLED`, `RETRY_WAIT` huérfano → `QUEUED`/`FAILED`. Audit en `jobs/<id>/logs/recovery.log` + eventos al bus.
- `job_state.py`: `RESOLVING` ahora permite `RETRY_WAIT` (recovery lo necesita; antes no tenía salida).
- Scheduler `_handle_failure` persiste `ExtractionError.detail` (stderr de yt-dlp/FFmpeg) a `jobs/<id>/logs/error.log` (escenario E: stderr disponible en diagnostics; ffmpeg ya no compromete output parcial — borra destination y clasifica non-retryable).
- Disk full ya clasificado `INSUFFICIENT_DISK` (yt-dlp classifier, non-retryable) + scheduler pausa dispatch con guarda de disco; red/timeout ya van por `NETWORK_ERROR`/`TIMEOUT` retryable con backoff acotado.
- Tests: `test_recovery.py` 9 nuevos (requeue, commit ambiguo, crash-loop FAILED, cancel muerto, retry revivido, sin plan, output COMPLETED intacto, log, bus).
- Gates: ruff+format clean, pyright 0, pytest 184 passed / 3 live skipped. `graphify update` corrido.

### Sesión 6 — 2026-10-06 — Fase 6 completada

- Scheduler asyncio + DefaultExecutor: budgets 3/2/1 por semáforos, cancelación cooperativa, retries con backoff vía RETRY_WAIT, chequeo de disco; EventBus SSE con replay e historia acotada; endpoints POST /api/v1/jobs, GET /api/v1/jobs[/{id}], POST .../cancel, GET /api/v1/events.
- Bug que bloqueó el cierre: starlette 1.7 TestClient bufea la respuesta completa → cuelga en streams infinitos (verificado en su código). Fix: _event_stream(bus) a nivel módulo en app.py, tests consumen el generador directo (→ Regla 6.1).
- Tests: 12 nuevos (test_scheduler.py 6 + test_events.py 6); acceptance 10-jobs-acotados, progreso normalizado, cancel, retry acotado, framing SSE.
- Gates: ruff + format clean, pyright 0, pytest 175 passed / 3 live skipped. JS sin cambios.

### Sesión 3 — 2026-10-04 — space-bunny-free vía OpenCode (PowerShell/Windows)

#### Fase 2 — SQLite + job state machine: completada

**Módulos nuevos en `apps/api`:**
- `job_state.py` — `JobState(StrEnum)` con los 14 estados del plan, tabla de
  transiciones válidas, `ACTIVE_STATES` (RESOLVING/DOWNLOADING/PROCESSING/
  VALIDATING/COMMITTING), `TERMINAL_STATES`, `can_transition`/`assert_transition`
  e `InvalidTransition` (fail explícito, nunca UNKNOWN_ERROR).
- `migrations.py` — migraciones append-only `(version, description, sql)` aplicadas
  con `PRAGMA user_version`. Migración v1 crea `jobs`, `job_events`, `settings` con
  las columnas del spec (incluye `source_url_hash`, `priority`, `attempt_count`).
- `db.py` — `connect()` (WAL, `foreign_keys=ON`, `synchronous=NORMAL`,
  `isolation_level=None`), `initialize()` idempotente, contextmanager `transaction()`
  con `BEGIN IMMEDIATE`/`ROLLBACK`/`COMMIT`, `schema_version()`.
- `jobs.py` — `Job` dataclass + repositorio: `create_job`, `get_job`, `list_jobs`,
  `transition` (valida, actualiza estado y graba el evento en la MISMA transacción),
  `find_active_jobs`, `get_events`, `hash_url`.

**Integración:** `app.py` ahora usa `lifespan` async — abre la DB al startup, loguea
`database_ready` con la versión de schema y la cierra al shutdown. `health` reporta la
DB real (`ok (schema v1)`) en vez del probe en memoria; se borró `database_ready()` de
`diagnostics.py` por quedar muerto.

**Tests (37 en total):** `test_job_state.py`, `test_db.py`, `test_jobs.py` (CRUD,
transición atómica con evento, transición ilegal no cambia el estado, ciclo completo a
COMPLETED, payload sin URL, filtros por estado, cascada al borrar, y recovery tras
"terminación del proceso"). `test_app.py` actualizado a fixture con lifespan.

**Dos tests fallaron al escribirlos (lección de diseño, no de código):**
1. Escribí `TERMINAL_STATES` incluyendo FAILED y un test que exigía "terminal sin
   salidas". Contradice el endpoint `POST /jobs/{id}/retry` del spec. Corrección:
   FAILED es terminal *para ese intento* y sólo puede reentrar explícitamente por
   `RETRY_WAIT`; el test ahora codifica esa excepción.
2. Conté mal los eventos del scenario de recovery (8 en vez de 7).

**Verificado en vivo contra `data/app.db`:** job real llevado a DOWNLOADING, cierre de
conexión simulando muerte del proceso, reapertura → el job aparece en
`find_active_jobs`, se reconcilia a RECOVERY_REQUIRED y luego a QUEUED (7 eventos).
`PRAGMA journal_mode` = `wal`, `user_version` = 1, en disco quedaron `app.db-wal` +
`app.db-shm`. Acceptance cumplida.

**Grafo:** `graphify update . --force` → 385 nodos, 568 aristas, 23 comunidades.

---

### Sesión 2 — 2026-10-04 — space-bunny-free vía OpenCode (PowerShell/Windows)

#### Fase 1 completada

**Backend ahora levanta solo.** Depends añadidas vía
`uv add --package local-media-downloader-api fastapi granian pydantic`.

**Archivos nuevos en `apps/api`:**
- `config.py` — `Settings` frozen dataclass; defaults loopback `127.0.0.1:8765`,
  `data_dir=./data`, `LMD_*` env overrides. Sin paths de usuario hardcodeados.
- `logging_config.py` — formatter JSON con campos spec `timestamp/level/component/event`,
  extras extraíbles.
- `diagnostics.py` — detección de tools vía subprocess argv fijos (`yt-dlp --version`,
  `ffmpeg/ffprobe -version`, `deno --version`), probe de sqlite `:memory:` y probe de
  escritura del data dir. No expone rutas absolutas.
- `app.py` — `create_app(settings)` factory, `GET /api/v1/health`, `GET /`, handlers
  estructurados (`NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL_ERROR`).
- `__main__.py` — entry `Granian(interface=Interfaces.ASGI, workers=1)`, script `lmd-api`
  en `[project.scripts]`.
- Tests: `test_config.py` (defaults loopback, env overrides, puerto inválido),
  `test_app.py` (health JSON, no leak de rutas, 404 estructurado, raíz apunta a health).

**Fixes durante Fase 1:**
- `ruff check` exigía `datetime.UTC` en vez de `timezone.utc` → auto-fix.
- Pyright falló: `LogLevels` vive en `granian.log`, no en `granian.constants`.
- 404 devolvía `{'detail': ...}` — el handler registraba `fastapi.HTTPException`, que no
  captura la excepción de Starlette del router. Se registró para
  `starlette.exceptions.HTTPException`, que sí cubre ambos.

**Verificado en vivo:** `uv run python -m local_media_downloader` en background →
`Invoke-RestMethod http://127.0.0.1:8765/api/v1/health` devuelve 200 con
yt-dlp 2026.08.19, FFmpeg 9.0.1, FFprobe 9.0.1 detected; yt-dlp-ejs y Deno
detected=false (esperado); database/storage ok; 125 GiB libres. JSON log
`{"timestamp":..., "level":"info", "component":"api", "event":"health_check"}` por stderr.

**Suite de Fase 1:** pytest 8/8, pyright 0, ruff/format clean, pnpm lint/check/test/build
verdes.

---

### Sesión 1 — 2026-10-04 — space-bunny-free vía OpenCode (PowerShell/Windows)

#### Fase 0 — Repository foundation: completada

**Decisiones tomadas con el usuario:**
- Fase 0 instala **sólo tooling** (pytest, httpx, Ruff, Pyright). FastAPI/Granian/Pydantic
  quedan para Fase 1; la acceptance "Backend starts locally" se difiere explícitamente.
- CI = GitHub Actions con matriz `ubuntu-latest` + `windows-latest` (Windows es target de
  packaging en Fase 16).

**Backend (`apps/api`)**
- `pyproject.toml` raíz: workspace uv con `apps/api` como miembro, dev group con
  httpx/pyright/pytest/ruff, y config de Ruff (line-length 100, `E,F,I,UP,B,SIM,RUF`),
  Pyright (`typeCheckingMode = "standard"`, venv `.venv`) y pytest (`testpaths`).
- `extend-exclude` de Ruff para `.agent/.claude/.opencode/data/graphify-out` — sin esto
  Ruff lint/formateaba los Python de los skills de `.opencode`.
- `apps/api`: paquete `local_media_downloader` (src layout, hatchling) +
  `tests/test_package.py`.
- `.python-version` = 3.12. `uv.lock` commiteado, `.venv` ignorado.

**Frontend (`apps/web`)** — scaffold `pnpm create vite` (svelte-ts) + Tailwind v4 vía
`@tailwindcss/vite`. Demo de Vite borrado (Counter, hero.png, logos, icons.svg, README,
`.gitignore` y `.vscode` propios). `App.svelte` reducido a un placeholder.

**Extensión (`apps/extension`)** — MV3 escrito a mano:
- `src/manifest.json` con permisos mínimos `activeTab` + `storage`, sin `host_permissions`.
- Adapter de browser: `src/browser/{types,chrome,firefox,index}.ts` (regla de
  ARCHITECTURE §10: el core no sabe en qué browser corre).
- Popup HTML+TS plano (la extensión NO usa Svelte), service worker `background/index.ts`.
- `vite.config.ts` con `entryFileNames` fijo para `background` y un plugin inline que
  copia `manifest.json` a `dist/` — se evitó `vite-plugin-static-copy` (dep extra).
- 4 tests Vitest sobre los bridges.

**Tooling raíz**
- `pnpm-workspace.yaml` (`apps/*`, `packages/*`), `package.json` raíz con scripts
  agregadores `lint` / `format:check` / `check` / `test` / `build`.
- ESLint 10 flat config (`@eslint/js` + `typescript-eslint` + `eslint-plugin-svelte` +
  `eslint-config-prettier`), Prettier 3 con plugins svelte + tailwindcss.
- `.gitattributes` (`* text=auto eol=lf`) + `.editorconfig` para LF consistente y
  eliminar el ruido de CRLF de `core.autocrlf=true` entre Windows y Ubuntu CI.
- `.github/workflows/ci.yml`: jobs `backend` y `frontend`, ambos con matriz de 2 OS.

**Gotcha documentado** → Regla de Oro 1.1: `uv sync` no instala miembros del workspace
salvo que el root los declare en `dependencies`.

**Verificación (local, todo verde):** `uv lock --check`, `ruff check`,
`ruff format --check`, `pyright` (0 errores), `pytest` (1), `eslint .`,
`prettier --check`, `svelte-check` + `tsc` (0 errores), `vitest run` (4),
`pnpm -r build` (web + extension).

**Sin commitear:** todo el trabajo quedó en el working tree; `git status` mostró además
que `docs/`, `.agent/`, `CLAUDE.md` y `graphify-out/` nunca fueron trackeados.

#### Auditoría de higiene del repo (mismo día)

Revisión de `.gitignore` con `git check-ignore` sobre ~34 rutas simuladas + grep de
secretos y de rutas absolutas en el código a commitear.

- **Secretos:** ninguno. Los hits de `api_key|token|secret|password` son texto de spec
  (`docs/TECHNICAL_SPEC.md` §22) y de skills de `.opencode/`. Cero credenciales.
- **Rutas absolutas hardcodeadas:** sólo `.claude/settings.json`
  (`C:/Users/SantiagoSL/.local/bin/graphify.EXE hook-guard ...`) → se ignora `.claude/`.
- **Bug encontrado y corregido:** al descomentar el bloque `# uv.lock` de la plantilla
  de Python, `uv.lock` pasó a estar **ignorado** — justo lo contrario de lo que CI
  necesita (`uv sync --locked`). Revertido; verificado con `git check-ignore uv.lock`
  → exit 1. Documentado como Regla de Oro 1.2.
- **`graphify-out/` ignorado:** son artefactos generados (incluye `cache/ast/` con
  cientos de JSON) y el hook post-commit los regenera. Ignorarlo también evita
  churn infinito en cada commit.
- **`.opencode/` ignorado:** librerías de skills vendorizadas (con `LICENSE.txt` de
  terceros); no es código del producto.
- **`.agent/` se versiona:** es memoria de proyecto, no config local.
- **Agregado:** `*.db*`, `*.sqlite*`, `*.env`, `*.local`, `*.pem`, `*.key`, `*.pfx`,
  `*.p12`, `*.tmp`, `*.bak`, `*.orig`, `*.rej`, `*.swp`, `*~`, `tmp/`, `temp/`,
  `coverage/`, `*.lcov`, `desktop.ini`, `ehthumbs.db`, `$RECYCLE.BIN/`, `*.lnk`,
  `*.code-workspace`.
- **Resultado:** de 190+ archivos sin trackear a 59, todos archivos fuente legítimos.
- **Observación abierta:** el `.gitignore` de plantilla tiene patrones peligrosos
  (`lib/`, `var/`, `build/`, `target/`) → cargada en `observations.md` para decidir en
  la Fase 1.

#### CI rojo en el primer push + capa de prevención

**Síntoma:** los 4 jobs de GitHub Actions fallaron. Causa real: `prettier --check .`
marcó `.github/workflows/ci.yml`; el único defecto era el **newline final ausente**
(`\ No newline at end of file`). Al crear el archivo después de la última pasada de
`pnpm format`, el formateador nunca lo había visto.

**Fix en dos capas:**
1. `pnpm exec prettier --write` sobre `ci.yml`.
2. `.pre-commit-config.yaml` con 3 hooks locales (`language: system`):
   `uv run --no-sync ruff format`, `uv run --no-sync ruff check` y
   `pnpm exec prettier --write --ignore-unknown`. Instalado con
   `uv run pre-commit install` → `.git/hooks/pre-commit`.
   `pre-commit>=4.0` agregado al dev group de uv (uv.lock actualizado).

**Verificado empíricamente en Windows** (no asumido):
- `uv run pre-commit run --all-files` → 3 hooks `Passed`.
- Sonda: un `zz-format-probe.json` mal formateado staged → el hook lo reescribió y
  `git commit` **abortó con exit 1**, sin crear commit. Sonda eliminada.

**También:** `README.md` reescrito con sección de setup de desarrollo (`uv sync`,
`pnpm install`, `uv run pre-commit install`) y los comandos de chequeo con paridad con
CI, para que un clone nuevo no vuelva a tropezar con esto.

**Suite completa verde antes de commitear:** `uv lock --check`, `ruff check`,
`ruff format --check`, `pyright` (0), `pytest` (1), `pnpm install --frozen-lockfile`,
`pnpm lint`, `pnpm format:check`, `pnpm check`, `pnpm -r test` (4), `pnpm build`.

→ Regla de Oro 1.3 (`lessons_learned.md`).

---

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

### Addendum 5 — Auditoría de SQL ( playbook cloud aplicado con criterio)

El usuario recomendó 6 prácticas de un proyecto previo (donde un mal indexado costó
500M de reads en Postgres serverless). Todas evaluadas **con medición, no de opinión**:
`EXPLAIN QUERY PLAN` + timing sobre 5.000 / 50.000 / 200.000 jobs.

**Se aplicaron (2, y ambas escondían algo real):**
- **Paginación por cursor sin `OFFSET`** → bug latente: `ORDER BY priority DESC,
  created_at` no tenía desempate único. `created_at` tiene resolución de milisegundos,
  así que un keyset cursor saltaba o duplicaba filas en los bordes de página. Ahora el
  orden es `(priority DESC, created_at DESC, id DESC)`, hay `JobCursor`/`cursor_of()` y
  `MAX_PAGE_SIZE=500`. Tests que fuerzan colisiones totales de `(priority, created_at)`
  para probar que no hay skips ni duplicados.
- **`idx_jobs_sort`** (migración v2) — el único índice más allá de columnas de WHERE/JOIN.
  Quita el TEMP B-TREE de `list_jobs`: página superficial **26.10 ms → 0.18 ms (145x)**,
  profunda 12.92 → 5.86 ms, a cambio de 3.7 → 4.0 µs/fila en transiciones (+8%).

**Se rechazaron con motivo escrito (4):**
- **Caché de endpoints** (`s-maxage`, CDN, Redis): no hay CDN — la app liga a loopback.
  Cachear el estado de jobs 60 s mostraría al usuario un job viejo, contradiciendo el
  progreso en vivo por SSE. Redis prohibido por principio #33. Lo que sí se agregó es lo
  opuesto: `Cache-Control: no-store` en todas las respuestas.
- **Connection pooling** (PgBouncer, Prisma Accelerate): es para Postgres serverless.
  Acá hay un worker Granian con una conexión SQLite en `app.state.db`.
- **Rate limiting con Upstash Redis**: los bots no rastrean 127.0.0.1. El riesgo real es
  una página web local pegándole a la API → Origin validation + token local, ya
  planificado para Fase 10.
- **Índices indiscriminados**: probé dos (`(state, priority, created_at)` y
  `(updated_at)`); NO quitaron el temp b-tree (un `IN` multi-estado no se sirve con un
  índice compuesto así) y costaron **3x** en escrituras (10.2 vs 3.5 µs/fila). Descartados.

**Dato de contexto que reencuadra todo:** el costo del escaneo total de `jobs` es 5k=1.0 ms
· 50k=11 ms · 200k=44 ms. El escaneo nunca fue el problema; **el sort sí**. Por eso la
regla de oro es: "SCAN TABLE" no es un bug por sí mismo, "TEMP B-TREE FOR ORDER BY" en una
consulta paginada sí lo es. → Regla de Oro 1.4.

**Nuevo test permanente:** `test_query_plans.py` asserta que los hot paths usan índice y
que `list_jobs`/cursor no tengan temp sort, con las mediciones documentadas en el
docstring para que nadie re-agre los índices descartados.

**Verificado:** migración v2 aplicada sobre `data/app.db` real (schema v1 → v2),
`list_jobs` en 0.03 ms. Gates: ruff, pyright 0, pytest 141/141.

### Chequeo final PROTOCOLO_SALIDA

- [x] 1 sola sesión en detalle (Sesión 4). Sesiones 1-3 comprimidas en historial con
      detalle verbatim en `session_log_archive.md`.
- [x] Sin duplicación Regla↔tech_stack: la narrativa vive sólo en
      `lessons_learned.md`; `tech_stack.md` referencia por número.
- [x] Loose ends de la sesión: ninguno.

---

### Sesión 5 — 2026-10-06 — Fase 4 + Fase 5 completadas

#### Addendum Fase 5 — Execution planner

- `domain/intent.py` — `OutputIntent` tipado (media/quality/container/audio/
  video_codec/processing) + `parse_intent` que rechaza keys desconocidas
  (no puede entrar un flag arbitrario de ffmpeg) y combos imposibles
  (video+mp3, audio=only con media=video).
- `domain/plan.py` — `ExecutionPlan`/`PlanStep` serializables
  (`execution_plan_json`, reproducible).
- `services/planner.py` — copy preferido; transcode solo si el contenedor
  fuente no satisface el intent (`_CONTAINER_ACCEPTS`); audio →
  `extract_audio` con codec por contenedor (mp3→libmp3lame, m4a→aac,
  opus→libopus, wav→pcm_s16le); remove audio → stream copy o transcode;
  resize/trim rechazados hasta Fase 14.
- `ErrorCode.UNSUPPORTED_INTENT` nuevo.
- Tests: 9 nuevos en `test_planner.py` (copy preferido, transcode solo
  necesario, webm source-compatible, mp3, remove audio, rechazo de keys
  arbitrarias y resize). Gates: ruff/format clean, pyright 0, pytest
  163 passed / 3 live skipped.

#### Qué se agregó (Fase 4)

- `domain/probe.py` — `MediaProbe`/`StreamProbe`/`StreamKind`, contrato
  normalizado sin schema de FFprobe; ausencia como `None` (§4).
- `domain/processor.py` — ports `MetadataInspector` y `MediaProcessor`
  (replaceable adapters, #24), con `name`/`version` + operaciones.
- `adapters/ffprobe.py` — `FFprobeInspector.inspect(path)` → `MediaProbe`;
  `parse_probe` puro y testeado; argv arrays, errores clasificados.
- `adapters/ffmpeg.py` — `FFmpegProcessor`: `remux` (`-c copy -map 0`),
  `transcode` (libx264/aac, veryfast), `extract_audio` (libmp3lame 192k),
  `video_only` (`-map 0:v:0 -c:v copy -an`), y `validate` (re-inspect +
  chequeos: existe, no vacío, streams presentes, duración > 0). Stream copy
  preferido; transcode solo cuando hace falta (#84). Timeout borra el
  destino parcial.
- `domain/errors.py` — `ErrorCode.VALIDATION_FAILED` nuevo.
- `adapters/tool_paths.py` — `_tool_argv` compartido; `ffprobe_argv()` con
  override `LMD_FFPROBE`, mismo orden que `LMD_FFMPEG`.

#### Decisiones

1. **La validación re-inspecciona el output con FFprobe** — exit code 0 de
   ffmpeg nunca declara archivo válido (#7); `validate` corre en el adapter.
2. **Los tests de aceptación usan ffmpeg real offline** (clip sintético
   lavfi, 1 s, 160x120) con `pytest.skip` si no están instalados — la
   Fase 3 probó que el fixture real detecta los bugs.
3. **`parse_probe` tolera strings numéricas de ffprobe** (`"duration":
   "12.3"`, fps como `"30000/1001"`) y streams desconocidos como `OTHER`.

#### Acceptance verificada (tests reales sobre clip sintético)

MP4 producido, MP3 producido, audio removido, remux, y metadata del output
validada vía FFprobe — todo verde con ffmpeg/ffprobe del PATH (scoop).

#### Gates

ruff + format clean, pyright 0, pytest 154 passed / 3 live skipped (141 → 154
con los 13 nuevos: 5 parse_probe + 8 acceptance ffmpeg). JS sin cambios.

### Sesión 11 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)

- Sesión de cierre/verificación (sin código de producto): `gh` CLI instalado vía scoop (2.102.0) + `gh auth login` hecho por el usuario → habilitó `gh run view --log-failed`, que antes daba 403 con la API pública.
- **CI: el job `frontend` estaba en rojo desde el commit de Fase 3** (los dos OS) y nadie lo había notado; `backend` pasaba. Causa raíz: pnpm **11 eliminó** `onlyBuiltDependencies` y lo ignora en silencio, así que el install limpio en CI abortaba con `ERR_PNPM_IGNORED_BUILDS` (deno) y su postinstall nunca corría — el runtime JS de yt-dlp-ejs tampoco estaba instalado en máquinas limpias. Localmente todo pasaba porque `node_modules` ya tenía el binario de instalaciones viejas.
- Fix: `pnpm-workspace.yaml` → `allowBuilds: { deno: true }`, verificado **antes** de pushear con un clon limpio (`git clone --depth 1`, borrar `node_modules`, correr los 5 pasos exactos del job frontend: install, lint, format:check, check, test, build). Commit `cbf8277`; CI quedó **4/4 verde** (run `37512262845`).
- Commit `8666100` con las fases 7–10 pusheado (un solo commit porque `app.py` mezcla las cuatro fases).
- **Fase 11 evaluada: NO se implementa Native Messaging.** El gate de `IMPLEMENTATION_PLAN.md` exige "instalación/distribución entendidas", y eso recién existe en Fase 16 (PyInstaller + Inno Setup). Además Native Messaging solo tiene sentido para builds instalados: el MVP localhost se comunica por HTTP loopback sin él. Se reevalúa en Fase 16.
- **Decisión explícita del usuario: no probar la extensión en un browser real hasta Fase 16.** Los riesgos que eso deja abiertos quedaron escritos como observación en curso (popup/CSP MV3, cookie `SameSite=Strict` contra el SSE, detección Chrome/Firefox del bridge) con el checklist para Fase 16.
- `roadmap.md` actualizado (Fase 11 como evaluada; corregida la referencia obsoleta a `onlyBuiltDependencies`; la nota de "docs/ sin trackear" ya no aplica porque `.agent/` está versionado).

### Sesión 14 — 2026-10-07 — cheap model (Fase 13) + opencode/muse-spark (verificación) vía OpenCode

- Modelo barato implementó Fase 13 con el prompt de 6 pasos + TESTING.md y paró correctamente ante ruff E501 con HANDOFF bien formado (primer drill real del stop-on-failure; el proceso quedó validado).
- **Fase 13 (Media presets):** contenedores `gif/webp/sticker/mobile` — `intent.py` (contenedores + reglas de audio), rama `CONVERT_PRESET` en planner, dispatch en executor (`_first_operation`/`_final_container`), `FFmpegProcessor.convert_preset` con autovalidación (validate + unlink), protocolos `MediaTool`/`MediaProcessor` ampliados; frontend: presets nuevos + `aria-label` + disclaimer WhatsApp; tests solo AGREGADOS (18 backend con ffmpeg real, 3 web + `Resolve.test.ts` nuevo), cero aserciones viejas tocadas.
- Fix del modelo caro: E501 en `ffmpeg.py:141` (f-string del filtro sticker partida). Gates verdes: pytest 326 passed/3 skipped, pyright 0, ruff clean, pnpm lint/format/check/test/build verdes (22 vitest ext + 88 web). Total: 439 tests.
- Nota de revisión: el planner también corrigió webm a VP9/Opus (antes libx264/aac en webm, no estándar); ningún test fijaba los códecs viejos. Commit `b4c10cf` + push.
- Próxima fase: 14 (Advanced processing).

### Sesión 15 — 2026-10-07 — opencode/muse-spark (fix + verificación) vía OpenCode

- HANDOFF Fase 14/trim: `test_trim_past_end_of_media_fails_validation` en rojo — `FFmpegProcessor._run` validaba sin limpiar (ramas timeout/exit≠0 sí hacían `unlink`); con `start=50` sobre 6 s ffmpeg sale 0 dejando archivo inválido y `validate` lanzaba sin borrarlo. Fix: `try/except ExtractionError → unlink + raise` en `_run` y en `_check_trimmed` (2 wraps, patrón ya usado en `convert_preset`); `validate()` sigue pura; test intacto, ningún test viejo tocado.
- Slice trim verificado (código del modelo barato, sin debilitar tests): `parse_trim` + validación en `parse_intent`, trim fuerza transcode con `trim_start/trim_end`, `TrimTool` opcional en executor, `transcode_trimmed`/`extract_audio_trimmed`/`_trim_args` en ffmpeg. DTO `processing` sin cambios → sin sync frontend. Resto de Fase 14 (crop/resize/bitrate/fps/subtítulos/metadata) pendiente por alcance.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 358 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 469 tests.
- Commit del slice + fix con push; `graphify update .` corrido.

### Sesión 16 — 2026-10-07 — opencode/muse-spark (fix resize + verificación) vía OpenCode

- HANDOFF Fase 14/resize: ruff E501 + 9 failed (378 passed). Raíz: `parse_resize` sin cotas y case-fold total (aceptaba `1280X720`/`99999x99999`); planner no rechazaba presets Fase 13 ni audio-only (resize se perdía en silencio); executor perdía resize cuando había trim (trim ganaba, sin combined); `_check_resized` solo validaba `Np`, no bbox; test de dimensiones asumía deformación exacta en vez de bbox.
- Fix quirúrgico: `parse_resize` con cotas (Np 1..4320, WxH 1..8192, `x` minúscula + `p` case-insensitive, fail-fast); planner rechaza resize en presets/audio-only/live; ffmpeg bbox (`force_original_aspect_ratio=decrease:force_divisible_by=2`, helper `_scale_filter`) + `_check_resized` valida Np y bbox (fits + touches ±2px) + `transcode_trimmed(resize_target)` single-pass; executor combinado trim+resize (exige `ResizeTool`, audio+resize rechazado); E501 partido.
- Tests: borrados con aprobación explícita del usuario `test_rejects_resize_until_phase_14` y `test_resize_is_still_rejected` (invariante temporal que Fase 14 reemplaza; resto intacto); `test_resize.py` nuevo: bbox 960x720 para 4:3, +4 audio-only, +1 trim+resize single-pass. DTO sin cambios → sin sync frontend.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 390 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 501 tests.
- Decisiones usuario: borrar (no reescribir) tests temporales — reescribir duplica cobertura de `test_resize.py`, borrar es limpio porque eran gates `until_phase_14`/`still_rejected`; bbox preserva aspect (nunca deforma).

### Sesión 17 — 2026-10-07 — opencode/muse-spark (fix crop + verificación) vía OpenCode

- HANDOFF Fase 14/crop: 6 failed, 428 passed. Doble raíz en `adapters/ffmpeg.py`: (1) `_crop_filter` emitía `crop=160x120` pero ffmpeg toma `w:h:x:y` con dos puntos → `Invalid chars 'x120'`; (2) tras arreglarlo, 2 fallos más — `_check_cropped` (match exacto de caja) corría sobre el archivo final del pass único crop+scale (960x720 vs caja 160x120).
- Fix quirúrgico: `_crop_filter` → `crop=w:h` / `crop=w:h:x:y`; check de caja exacto solo cuando `resize_target is None` en `crop()` y `transcode_trimmed()` (un pass único produce un solo archivo: solo la geometría final es observable; ffmpeg falla ruidoso si la caja excede el frame, y `_check_resized` sigue validando el bbox final). Orden crop-antes-de-scale intacto (caja en coords de origen). `_crop_size` sin cambios.
- Sin tests debilitados: diffs en `test_trim/test_resize` solo agregan `"crop": None` al `as_dict` (expansión de contrato por el campo nuevo de `Processing`); contratos backend + frontend ya sincronizados en el slice (ambos verdes). Los tests que blindan el fix ya existían en `test_crop.py` nuevo (exact box, offset, one-pass, trim+crop+resize).
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 434 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 545 tests.
- Pendientes Fase 14: bitrate, framerate, codec, subtítulos, metadata, audio normalization.

### Sesión 18 — 2026-10-07 — opencode/z-ai-glm-5.3 (fix encode-options + verificación) vía OpenCode

- HANDOFF Fase 14/encode-options: pyright en rojo (2 errores en `services/executor.py`). Raíz: `VideoEncodeOptionsTool` (protocolo runtime_checkable) redeclaraba `transcode`, nombre que `MediaTool` ya tiene → isinstance sólo prueba presencia (todo MediaTool lo tiene, stubs viejos incluidos → guardián muerto, bug latente) y en la intersección el unpack `**_EncodeKwargs` no matcheaba la firma de MediaTool. Pyright señalaba un bug real, no ruido. → **Regla de Oro 14.1**.
- Fix quirúrgico (solo executor.py): `_supports_encode_options()` verifica la firma real con `inspect.signature(processor.transcode).parameters` (keywords `video_bitrate`/`video_framerate`); la llamada va por `cast(VideoEncodeOptionsTool, ...)` con una única rama TRANSCODE (if/else duplicado eliminado); el protocolo dejó de ser `runtime_checkable` y su docstring documenta por qué. `intent.py`: comentario obsoleto de `video_codec` actualizado. Cero tests viejos tocados.
- Tests nuevos en `test_encode.py` (blinden el diseño): executor forwardea bitrate/framerate a un processor con firma extendida; processor legacy + sin opciones → transcode normal sigue; processor legacy + opciones → `UNSUPPORTED_INTENT` sin llamada.
- Slice verificado sin debilitar nada: planner emite `video_codec` base (`libvpx-vp9` webm / `libx264` resto) que `**encode` sobreescribe solo con codec explícito — tests del modelo barato ya eran consistentes; no hizo falta tocar planner. DTO crece (`video_bitrate`/`video_framerate` opcionales) pero no está expuesto en `_job_dict` → sin sync de `test_contracts.py`/`schemas.ts`; `packages/contracts/src/index.ts` ya actualizado.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 491 passed/3 skipped + smoke 1 passed (ffmpeg local tiene libsvtav1 → tests av1 corren), pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 605 tests.
- Pendientes Fase 14: subtítulos, metadata, audio normalization.

### Sesión 19 — 2026-10-07 — opencode/meta/muse-glimmer-30b (audio normalization Fase 14) vía OpenCode

- HANDOFF Fase 14/audio normalization: implementado slice de normalización de audio con loudnorm.
- Cambios: `domain/intent.py` añade `audio_normalize` bool; `domain/plan.py` detalle dict[str,str]; `services/planner.py` propaga `audio_normalize` en plan steps; `adapters/ffmpeg.py` añade `audio_normalize` param a transcode/resize/crop/extract_audio y aplica `-af loudnorm=I=-14:LRA=11:TP=-1.5`; `services/executor.py` forward `audio_normalize` a llamadas de procesador, actualizados protocolos `VideoEncodeOptionsTool`, `TrimTool`, `ResizeTool`, `CropTool`.
- Fix de tipos y line-length, actualización de stubs de tests `test_encode.py` y `test_scheduler.py`.
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 491 passed/3 skipped.
- Pendientes Fase 14: subtítulos, metadata.

### Sesión 20 — 2026-10-07 — opencode/moonshotai/kimi-k3 (auditoría + fix del slice audio normalization Fase 14) vía OpenCode

- Auditoría del HANDOFF Sesión 19: gates del handoff verdes reales, pero el slice tenía 4 problemas: (1) `audio_normalize=True` con fuente copy-compatible caía en REMUX (`-c copy`) → loudnorm nunca se aplicaba (degradación silenciosa, el caso más común mp4→mp4); (2) combos `audio=remove` y presets gif/webp/sticker/mobile llevaban la key como detalle muerto en vez de rechazarse; (3) el executor pasaba `audio_normalize=` incondicional a `transcode` (rompía procesadores con firma Fase 4, compatibilidad documentada de la Regla 14.1) y lo enmascaró agregando `**kwargs` al stub `_LegacyTranscoder` (test viejo debilitado); (4) cambio ajeno de fase en `_step_from_dict` de scheduler.py.
- Fix quirúrgico: `_full_video_plan` incluye `not intent.audio_normalize` en `compatible` (fuerza TRANSCODE, igual que trim/resize/crop/encode); planner rechaza normalize para `audio=remove` y presets (UNSUPPORTED_INTENT); keys muertas fuera de REMUX/VIDEO_ONLY. Executor: `_NormalizeKwarg` TypedDict + `_supports_audio_normalize` (inspección de firma, mismo patrón que `_supports_encode_options`) — kwarg solo se reenvía si fue pedido; pedido-pero-no-soportado → UNSUPPORTED_INTENT. `_LegacyTranscoder` restaurado a su firma Fase 4 (test honesto de nuevo); `_step_from_dict` revertido a coerción `str()` (mantiene la garantía runtime de `PlanStep.detail: dict[str, str]`).
- Feature blindada con la matriz de capability que §528 de IMPLEMENTATION_PLAN exige: `tests/test_audio_normalize.py` nuevo (27 tests) — parse (bool estricto, rechaza "true"/1/None), matriz planner (fuerza transcode, copy sin la key, extract_audio, combo trim, rechazos remove/presets), forwarding executor (transcode/extract_audio, rechazo legacy + kwarg omitido en legacy), argv del adapter con ffmpeg real (loudnorm llega a transcode/extract_audio/trimmed/resize/crop; nunca con `audio_codec="none"`).
- Sin sync frontend: backend-only igual que slices trim/resize/crop/encode (la key es opcional; `OutputIntent.as_dict()` no alimenta ningún DTO de respuesta).
- Gates TODO VERDE: ruff check+format clean, pyright 0, pytest 518 passed/3 skipped (fast) + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build verdes. Total: 629 tests.
- Pendientes Fase 14: subtítulos, metadata.

### Sesión 22 — 2026-10-08 — opencode/muse-spark (cierre Fase 15 Performance engineering) vía OpenCode

- Fase 15 es medición manual sin tests nuevos. `docs/TESTING.md` §8: gates unchanged, mediciones fuera de suite.
- Medición manual de startup: servicio en puerto aislado con `LMD_DATA_DIR` temporal, Stopwatch hasta `/api/v1/health` 200. Resultados: ~10.29-10.31 s, WorkingSet ~22.5 MB.
- Gates verificados y verdes: `uv run ruff check/format`, `uv run pyright` 0, `uv run pytest -m "not smoke"` 534 passed/3 skipped, `uv run pytest -m smoke` 1 passed; `pnpm lint/format:check/check/test/build` verdes.
- Sin cambios de código; sin modificación/borrado de tests existentes. Fase 15 marcada como ✅ en `roadmap.md` e `INDEX.md` actualizado a Próxima fase 16.
- Nota de Sesión 23: la medición de memoria era de un solo proceso (refutada: árbol real ~82 MB WS) y quedaron restos sin commitear (`measure_startup.py` + `data_perf_test/`); ver Sesión 23.

### Sesión 23 — 2026-10-08 — opencode/muse-spark (verificación HANDOFF + cierre real Fase 15) vía OpenCode

- Verificación del HANDOFF Sesión 22: `git status/diff` solo tocaba memoria (3 archivos), cero código/tests → ningún test debilitado. Pero la medición era incompleta: script `measure_startup.py` sin commitear (puerto fijo 18765, viola Regla 10.2; pipe de stdout sin drenar; claimaba WorkingSet sin medirlo) + `data_perf_test/` vacío → ambos eliminados del repo.
- Re-medición hermética (puerto fresco con ownership, `LMD_DATA_DIR` temporal): boot→listen 0.56–1.64 s, →first `/health` 200 10–22 s (delta ~12.5 s = tool probes del health en frío); memoria del ÁRBOL 81.6–82.0 MB WS / 67–69 MB privada (3 python: launcher ~4 + Granian ~28 + worker ~49) → 22.5 MB refutado. Import app ~0.6–1.2 s (domina fastapi). API: health med 3 ms p95 17 ms; jobs-list med 3 ms p95 17 ms. Cola (in-process, stub extractor + scheduler real, n=10): pickup med 13.3 ms p95 15 ms. SQLite: 2000 inserts 155 ms single-txn / 11 ms batch, keyset page 0.041 ms. Disco 349/1377 MB/s. FFmpeg synth 480p5s 0.33 s ≈457 fps. UI `dist` 108190 B.
- No medible offline por diseño: download throughput (crear jobs resuelve vía yt-dlp real; `.invalid`→502) y cola sobre HTTP real → diferido a red en vivo (TESTING.md §5, `observations.md`). Sonda de cola casi falla por saturar `max_active=3` con executor que nunca termina (lección: liberar slot con cancel entre muestras). Tuning: SIN cambios — headroom en todos los knobs (Granian workers=1, scheduler 3/2/1, threads FFmpeg); el único costo (probes del primer health) es diagnóstico por diseño, cachearlo cambiaría el contrato → observación abierta para Fase 16/17.
- Gates re-corridos en orden TODO VERDE: ruff check+format (83 files), pyright 0, pytest 534 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build. Total 645. Sin cambios de código; sin tests nuevos (§8) ni viejos tocados.
- Memoria rotada (22→archive verbatim + historial); `roadmap.md` ref→Sesión 23; `INDEX.md` honesto (download-throughput diferido); `observations.md` +2 abiertas; `graphify update .` + commit + push. Siguiente: Fase 16 Packaging.

### Sesión 24 — 2026-10-08 — opencode/muse-spark (revisión HANDOFF Fase 16 Packaging) vía OpenCode

- Revisión del HANDOFF: `git status/diff` mostraba solo código (pyproject, tool_paths, uv.lock) + 2 untracked, cero tests tocados → ningún test debilitado. Pero el deliverable era irreproducible: `lmd.spec` con ruta absoluta hardcodeada + gitignored por `*.spec` (no commiteable), `config._DEFAULT_WEB_DIST` no frozen-aware (bundle corría headless aunque llevara `web/`), `installer.iss` con rutas relativas al dir equivocado, `pydantic_settings` en hiddenimports sin ser dependencia, `web/` duplicado en el bundle, FFmpeg sin stagetear.
- Fixes: `lmd.spec` portable (anclado a SPECPATH, fail-fast si falta web dist, sin datas redundantes, `exclude_binaries=True`); `!apps/api/lmd.spec` en `.gitignore`; `config.default_web_dist()` frozen-aware (exe_dir/web → _MEIPASS/web → dev); `_bundle_bin_candidates()` calculado por llamada; `lmd_entry.py` shim (el spec corría `__main__.py` top-level y los imports relativos reventaban en frozen: `ImportError`, cazado al bootear el bundle); `installer.iss` con rutas `..\`; `packaging/stage_bundle.ps1` (deno del pnpm store + resuelve shims de scoop al binario real; FFmpeg gyan full 9.0.1 local); notices con versiones exactas. Test nuevo `test_packaging_paths.py` (7 tests, viejos intactos).
- Verificación: bundle PyInstaller 6.22.3 onedir recompilado 2 veces OK con el spec portable; el primer boot frozen falló (motivo del shim), el segundo quedó colgado en smoke y dejó 5 ffmpeg zombie → matados, `dist/`+`build/` (~600 MB, todo gitignored) eliminados por presión de RAM del usuario. Smoke del bundle final y checklist de browser real quedan PENDIENTES → Fase 16 sigue ABIERTA.
- Gates dev TODO VERDE: ruff (77 files), pyright 0, pytest 541 passed/3 skipped (534 + 7 nuevos) + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web)/build. Nota: `uv sync --extra build` desde `apps/api` podó las dev deps (ruff/pytest/pyright desaparecieron del venv) → `uv sync --all-packages` lo restauró; desde repo root usar `uv run --package local-media-downloader-api --extra build`.
- Decisión del usuario: commitear solo lo liviano (binarios nunca se versionan) y no reintentar el bundle ahora. Siguiente: smoke del exe frozen + checklist browser (observations.md) para cerrar Fase 16.

### Sesión 25 — 2026-10-08 — opencode/muse-spark (cierre Fase 16 con reservas de hardware) vía OpenCode

- Procesos: 24 `python.exe` del Python del sistema (`AppData\Programs\Python312`, NO del `.venv` del proyecto), todos hijos `multiprocessing.spawn` huérfanos (0/24 padres vivos), 4–15 MB c/u. No son del proyecto → no se tocan. Sin restos del bundle (exe/ffmpeg limpio). `dist/`+`build/` eliminados (gitignored).
- Cierre Fase 16 con 2 reservas documentadas (la laptop no aguanta el smoke del bundle: 2 intentos caídos por recursos): (1) smoke del exe frozen — compilación probada 3× OK, boot real pendiente en máquina con resto/CI; (2) checklist browser real (Chrome/Firefox) — requiere humano, 5 minutos. Cómo re-verificar: `pnpm build` + pyinstaller con spec + `stage_bundle.ps1` + boot con `LMD_DATA_DIR` temporal (comandos en observations.md). Sin cambios de código en esta sesión; gates dev ya verdes sobre el mismo árbol (Sesión 24).
- `uv run --package local-media-downloader-api --extra build` desde repo root: compila sin podar dev deps (lección Sesión 24).
- Memoria rotada (24→archive verbatim + historial); `roadmap.md` Fase 16 ✅ con reservas; `graphify update .` + commit + push. Siguiente: Fase 17 Release hardening (y las 2 reservas cuando haya máquina/restos).

### Sesión 26 — 2026-10-08 — opencode/muse-spark (revisión HANDOFF + cierre Fase 17) vía OpenCode

- Revisión del HANDOFF: `git status/diff` mostraba 1 archivo sin commitear (`test_scheduler.py`, +42, cero código) → ningún test viejo debilitado. Pero el test nuevo era débil: aceptaba `FAILED` además de `CANCELLED` (enmascara un path de cancelación roto), no verificaba orphans, imports inline y sin `try/finally` para `scheduler.stop()`.
- Fix quirúrgico solo al test: `test_cancel_running_job` ahora exige `CANCELLED` estricto + `executor.active_run == 0` + `scheduler._active == {}` + `scheduler._cancels == {}` (blinda cancel-running y no-orphans); estable 5/5 corridas. Sin cambios de contrato (test-only, sin sync frontend).
- Gates TODO VERDE en orden: ruff check+format (77 files), pyright 0, pytest 542 passed/3 skipped + smoke 1 passed, pnpm lint/format:check/check/test (22 ext + 88 web = 110)/build. Total 653. Fase 17 marcada ✅ en `roadmap.md`; las 2 reservas de Fase 16 (smoke bundle + browser real) siguen abiertas en `observations.md`.
- Memoria rotada (25→archive verbatim + historial); `graphify update .` + commit + push. Siguiente: reservas de hardware cuando haya máquina/restos + humano para browser.

### Sesión 27 — 2026-10-08 — opencode/muse-spark (CI ubuntu en verde + trial browser) vía OpenCode

- Trial browser: servidor levantado desacoplado (WMI, el harness mata el árbol del comando al terminar) en 127.0.0.1:8765 con `LMD_DATA_DIR` temporal; health 200 + shell con `<meta lmd-token>` verificados. Lección: `Start-Process` no sobrevive al fin del comando, WMI sí.
- `gh run list`: CI rojo desde Fase 13, solo `backend ubuntu-latest` (windows + frontend verdes). `--log-failed`: smoke fallaba con `resolve` de `.invalid` → 503 TOOL_OUTDATED, el test exige {502, 504}.
- Root cause: glibc dice "Name or service not known", Winsock "getaddrinfo failed" — `_NETWORK` no conocía la variante Linux y la línea caía en `_BROKEN_EXTRACTOR`. Bug real, no test débil.
- Fix: `_NETWORK` +3 variantes + 2 filas de regresión glibc en `test_adapter_errors.py` (viejos intactos); Regla 17.1, 12.x→archive. Gates: ruff/pyright/pytest 544 passed + smoke 1. Total 655. Commit + push, CI vigilado 4/4 verde.
- Nota: en CI ubuntu hay 40 skips "ffmpeg/ffprobe not installed" (no tumban el build, pero esa cobertura solo corre en Windows/local). Propuesta: instalar ffmpeg en el job ubuntu.

### Sesión 28 — 2026-10-08 — opencode/muse-spark (ffmpeg CI ubuntu + fix 403 dev) vía OpenCode

- Usuario pidió: ffmpeg en el job backend de CI + apagar servidor de prueba (PID 13724 ya inexistente; :8765 lo tenía su propio backend). Reportó 403 en `/api/v1/jobs` y `/api/v1/events` desde :5173.
- Root cause 403: proxy Vite con `changeOrigin: false` → backend veía `Host: 127.0.0.1:5173`, `validate_host(expected_port=8765)` rechazaba por puerto. Fix: `changeOrigin: true` + comentario que cita el check (Regla 17.2). En dev el token va por cookie (abrir :8765 una vez la fija).
- CI: paso `Install FFmpeg (ubuntu)` solo en ubuntu → ~40 skips pasan a correr. Gates frontend re-corridos (lint/format:check/check/test 110/build verdes). Commit + push, CI vigilado 4/4.

### Sesión 29 — 2026-10-08 — opencode/muse-spark (sticker webp interop + CI 4/4 con cobertura total) vía OpenCode

- Instalar ffmpeg en CI ubuntu destapó `sticker-webp` rojo: ffprobe 0x0 + decoder "Decode error rate 1" con archivo VÁLIDO (canvas VP8X 512x512, 10 KB). Forense local (BtbN 8.1): libwebp emite ANMF sub-frames con offset (recorta bordes transparentes del pad) y el decoder nativo ≤8.x los rechaza; 9.x sí los lee.
- Fix en 2 partes: (1) CI ubuntu+windows con BtbN n9.0 static pineado (misma clase que el bundle 9.0.1; apt no servía y johnvansickle-7.0.2 no trae libsvtav1 que exige el test AV1); (2) robustez real: dims 0→None en parse (contrato probe.py) + fallback coded + `validate()` rellena dims desconocidas desde frames decodeados (showinfo, fail closed) + warning con actuals en el breach.
- CI final 4/4 verde: 547 passed en AMBOS OS (0 skips ffmpeg; solo 3 live opt-in). Total 657. Regla 17.3. Build 8.1 temporal (~200 MB) eliminado del TEMP.
