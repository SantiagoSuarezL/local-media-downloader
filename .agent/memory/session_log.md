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

`Sesión 1 — 2026-10-04 — space-bunny-free vía OpenCode (PowerShell/Windows)`

### Fase 0 — Repository foundation: completada

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
- `apps/api`: paquete `local_media_downloader` (src layout, hatchling) + `tests/test_package.py`.
- `.python-version` = 3.12. `uv.lock` commiteado, `.venv` ignorado.

**Frontend (`apps/web`)** — scaffold `pnpm create vite` (svelte-ts) + Tailwind v4 vía
`@tailwindcss/vite`. Demo de Vite borrado (Counter, hero.png, logos, icons.svg, README,
`.gitignore` y `.vscode` propios). `App.svelte` reducido a un placeholder.

**Extensión (`apps/extension`)** — MV3 written a mano:
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

**Gotcha documentado** → Regla de Oro 1.1 (`lessons_learned.md`): `uv sync` no instala
miembros del workspace salvo que el root los declare en `dependencies`.

**Verificación (local, todo verde):** `uv lock --check`, `ruff check`, `ruff format --check`,
`pyright` (0 errores), `pytest` (1), `eslint .`, `prettier --check`, `svelte-check` + `tsc`
(0 errores), `vitest run` (4), `pnpm -r build` (web + extension).

**Sin commitear:** todo el trabajo está en el working tree; `git status` muestra además
que `docs/`, `.agent/`, `CLAUDE.md` y `graphify-out/` nunca fueron trackeados.

### Addendum — auditoría de higiene del repo (mismo día)

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
- ** agregado:** `*.db*`, `*.sqlite*`, `*.env`, `*.local`, `*.pem`, `*.key`, `*.pfx`,
  `*.p12`, `*.tmp`, `*.bak`, `*.orig`, `*.rej`, `*.swp`, `*~`, `tmp/`, `temp/`,
  `coverage/`, `*.lcov`, `desktop.ini`, `ehthumbs.db`, `$RECYCLE.BIN/`, `*.lnk`,
  `*.code-workspace`.
- **Resultado:** de 190+ archivos sin trackear a 59, todos archivos fuente legítimos.
- **Observación abierta:** el `.gitignore` de plantilla tiene patrones dangerous
  (`lib/`, `var/`, `build/`, `target/`) → cargada en `observations.md` para decidir en
  la Fase 1.

### Chequeo final PROTOCOLO_SALIDA

- [x] `session_log.md` con 1 sola sesión en detalle (rotación no aplica aún: el archivo
      de archive estaba vacío).
- [x] Sin duplicación Regla↔tech_stack: la narrativa de 1.1 y 1.2 vive sólo en
      `lessons_learned.md`; `tech_stack.md` referencia por número.
- [x] Lo movido a `_archive.md`: nada en esta sesión.

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

(vacío)