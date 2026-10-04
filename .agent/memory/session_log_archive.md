# Session Log — ARCHIVO — local-media-downloader

> Detalle completo verbatim de sesiones pasadas. No se lee automático.
> Consultar solo si hace falta el detalle exacto de archivos/tests/decisiones
> de una fase vieja.

## Archivo de sesiones

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