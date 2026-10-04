# Tech Stack — local-media-downloader

> Se completa la primera vez durante el bootstrap (ver BOOTSTRAP.md),
> leyendo ARCHITECTURE.md/TECHNICAL_SPEC.md UNA vez. Después de eso, este
> archivo se actualiza SOLO si un cambio de stack/arquitectura es inamovible
> (ver PROTOCOLO_SALIDA.md §1) — no en cada sesión.

## Stack Actual

**Lenguaje:** Python 3.12+ (backend), TypeScript (frontend/extension)

**Dependencias principales:**
- Backend: FastAPI, Granian, Pydantic, SQLite (stdlib, WAL), yt-dlp + yt-dlp-ejs + Deno (runtime JS interno del extractor), FFmpeg/FFprobe (binarios externos)

**Resolución de binarios (no depender del PATH global):**
- `yt-dlp` 2026.8.19 es dependencia **Python** del uv env; se invoca siempre como `[sys.executable, "-m", "yt_dlp", ...]`, jamás como `yt-dlp` del PATH.
- **Deno 2.9.6 vía pnpm** (devDependency raíz + `onlyBuiltDependencies: [deno]` en `pnpm-workspace.yaml`, porque su binario se descarga en postinstall y pnpm los bloquea). Se le pasa a yt-dlp con `--js-runtimes deno:<path>`.
- Orden de búsqueda en `adapters/tool_paths.py`: override explícito → `node_modules/.bin` del workspace → venv del uv → PATH. En producción (Fase 16) el orden pasa a ser bundle → venv → PATH.
- FFmpeg/FFprobe: `LMD_FFMPEG` > venv del uv > PATH.
- Frontend: Svelte 5, Vite, TypeScript, Tailwind CSS, pnpm
- Extension: TypeScript, Manifest V3, Vite
- Monorepo: uv + `.venv` + `uv.lock` (Python), pnpm (TS, único package manager JS)

**Arquitectura:**
```text
local-media-downloader/
├── apps/
│   ├── api/        # FastAPI + Granian (src/, tests/, pyproject.toml)
│   ├── web/        # Svelte 5 + Vite + Tailwind (assets estáticos servidos por FastAPI)
│   └── extension/  # TS MV3, Vite, browser/ chrome|firefox adapter
├── packages/
│   └── contracts/
├── docs/
├── data/           # app.db, jobs/<job-id>/{source,work,output,logs}, cache/, logs/
├── pyproject.toml
├── uv.lock
├── pnpm-workspace.yaml
└── README.md
```
Monolito modular local-first con scheduler durable de jobs (asyncio, sin Celery/RQ/Redis). API no contiene lógica yt-dlp/FFmpeg; workers ejecutan subprocesos aislados; SQLite solo metadata/estado (nunca bytes de media). Progreso en tiempo real vía SSE (`GET /api/v1/events`); acciones del usuario vía HTTP. En producción FastAPI sirve el build estático de Svelte — sin servidor Node en runtime.

**Configuración tooling:** uv (env/deps), pytest + httpx (Pyright para types, Ruff lint+format), Vite (frontend/extension); ESLint 10 + typescript-eslint + eslint-plugin-svelte, Prettier 3 (svelte + tailwind plugins), Vitest 5 (tests JS), `pre-commit` 4 (hooks ruff+prettier); no mypy, no watchfiles en runtime. CI = GitHub Actions con matriz `ubuntu-latest` + `windows-latest`.

**Checks (paridad con CI):** `uv run ruff check . && uv run ruff format --check .`, `uv run pyright`, `uv run pytest`, `pnpm lint`, `pnpm format:check`, `pnpm check`, `pnpm test`, `pnpm build`.

**Packaging:** Windows primero — PyInstaller onedir → Inno Setup. Binarios third-party bundled y pineados (FFmpeg LGPL preferible); THIRD_PARTY_NOTICES.md; licencia del proyecto Apache-2.0.

**Suite de tests:** 135 (128 pytest en `apps/api` + 4 Vitest en `apps/extension` + 3 pytest live opt-in con `LMD_LIVE_NETWORK=1`; `apps/web` sin tests todavía)

---

## Protocolos Críticos (Inamovibles)

> Protocolos Críticos solo para invariantes que costó aprender — no transcribir
> el spec. Regla corta y prescriptiva acá. La historia completa (bug, root
> cause, código) vive en `lessons_learned.md` o `lessons_learned_archive.md` —
> referenciada por número `(Ref: X.Y)`, nunca repetida palabra por palabra.

1. Un miembro del workspace uv sólo queda instalado con `uv sync` si el root lo declara en `dependencies` + `[tool.uv.sources] { workspace = true }`. (Ref: 1.1)
2. `apps/web` y `apps/extension` se compilan a assets estáticos; el manifest MV3 y el `index.html` del popup se copian a `dist/` con paths fijos (`src/background/index.js`, `src/popup/index.html`) que el manifest referencia literalmente.
3. `uv.lock` y `pnpm-lock.yaml` se versionan; CI usa `uv sync --locked` y `pnpm install --frozen-lockfile`. Ningún lockfile puede quedar ignorado. (Ref: 1.2)
4. `.gitignore` ignora `.claude/`, `.opencode/` y `graphify-out/` (config de agente con rutas absolutas de la máquina y artefactos generados). `.agent/memory/` sí se versiona.
5. Todo archivo nuevo o editado debe pasar por su formateador (`uv run ruff format`, `pnpm exec prettier --write`) ANTES de commitear: el hook `pre-commit` lo exige y CI lo revalida. (Ref: 1.3)
6. Base de datos: `data/app.db` en WAL + `foreign_keys=ON` + `synchronous=NORMAL`, `isolation_level=None` con transacciones `BEGIN IMMEDIATE` explícitas, migraciones append-only versionadas con `PRAGMA user_version`. Conexión única en `app.state.db` creada en el lifespan y cerrada al shutdown. `jobs.state` es la única fuente de verdad; `job_events` es audit sin URLs completas (solo `source_url_hash`).
7. Capas: `domain/` (modelos, `ErrorCode`, puertos, política de URLs) no importa nunca yt-dlp ni FastAPI; `adapters/` es el único lugar que conoce herramientas externas; `services/` orquesta; `app.py` sólo valida y delega. La validación de URL se aplica en el **service**, no en el adapter, para que ninguna implementación del puerto pueda saltársela.
8. `quality_score` ordena candidatos para el planner pero jamás declara más calidad de la que tiene la fuente: la resolución domina y "combined" sólo desempata (un 360p muxed no puede ganarle a un 1080p video-only).
9. `list_jobs` pagina por cursor (keyset) sobre `(priority DESC, created_at DESC, id DESC)`; nunca `OFFSET`. El `id` al final es obligatorio: `created_at` tiene resolución de milisegundos y sin desempate único el cursor salta o duplica filas. Índice `idx_jobs_sort` (migración v2) elimina el TEMP B-TREE: página superficial 26.10 ms → 0.18 ms a cambio de +8% en escrituras. `MAX_PAGE_SIZE=500`. Todas las respuestas de API llevan `Cache-Control: no-store` (loopback, estado en vivo, sin CDN).
