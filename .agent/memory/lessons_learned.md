# Lessons Learned — local-media-downloader

> MEMORIA ACTIVA. Se lee completa al inicio de sesión.
> Reglas de fases viejas: ver `lessons_learned_archive.md` (NO se lee
> automático, solo por grep/keyword si la tarea actual toca esa fase).
> Regla de rotación: este archivo debe contener solo las reglas de las
> últimas 2 fases. Al cerrar una fase nueva, la más vieja de las que
> quedan acá pasa al archivo y se reemplaza por una línea de índice abajo.

## Índice de reglas archivadas

(vacío todavía)

---

## Reglas activas

### Regla de Oro 1.1 [Tooling / uv]: `uv sync` NO instala miembros del workspace por defecto

**Error:** tras crear `apps/api` como miembro de `[tool.uv.workspace]`, `uv sync` resolvió el lock y creó `.venv` pero NO instaló `local-media-downloader-api`; `pytest` falló con `ModuleNotFoundError: local_media_downloader`.

**Root Cause:** en un workspace uv, los miembros no se instalan al entorno por sí solos. Sólo entran si el proyecto raíz los declara en `dependencies` (con `[tool.uv.sources] … = { workspace = true }`) o si se pasa `uv sync --all-packages`.

**Solución:** `pyproject.toml` raíz ahora declara `dependencies = ["local-media-downloader-api"]` + `[tool.uv.sources]`. `uv sync` a secas instala el editable y `pytest`/`pyright` ven el paquete.

**Regla de Oro:** *Todo miembro del workspace uv que los tests importen debe declararse en `dependencies` del root con `tool.uv.sources`; nunca confíes en que `workspace.members` instala solo.*

### Regla de Oro 1.2 [Git / reproducibilidad]: los lockfiles se versionan, siempre

**Error:** al agregar la sección de proyecto al `.gitignore` (que viene de una plantilla de Python con ~220 líneas), se descomentó `uv.lock` — o sea, se empezó a **ignorar** el lockfile.

**Root Cause:** las plantillas de `.gitignore` de Python vienen con `# uv.lock`, `# poetry.lock` etc. comentados como recordatorio de que "en general se versionan". Descomentar ese bloque achieves el contrario de lo que dice el comentario.

**Solución:** `uv.lock` quedó versionado (comentario explícito en la línea 102 del `.gitignore`); `pnpm-lock.yaml` también. Verificado con `git check-ignore uv.lock` → exit 1.

**Regla de Oro:** *Nunca aceptes el default de un `.gitignore` heredado para los lockfiles: `uv.lock` y `pnpm-lock.yaml` se commitean siempre, y verificá con `git check-ignore` antes de dar por cerrada la higiene del repo.*

### Regla de Oro 1.3 [Proceso / formateo]: formatear SIEMPRE después de escribir un archivo

**Error:** el primer push a GitHub dejó los 4 jobs de CI en rojo. `prettier --check .`
fallaba por `.github/workflows/ci.yml` y, en el fix, por `.pre-commit-config.yaml`. En
ambos casos el único defecto era **falta el newline final** (`\ No newline at end of file`).

**Root Cause:** la herramienta de escritura de archivos no garantiza el newline final, y
además yo escribí esos archivos *después* de la última pasada de `pnpm format`. El
resultado es que el formateador nunca los vio, pero CI sí.

**Solución:** dos capas. (1) `.pre-commit-config.yaml` con hooks locales de `ruff format`,
`ruff check` y `prettier --write`, instalados con `uv run pre-commit install`; verificado
en Windows — un commit con un JSON mal formateado aborta con exit 1. (2) Los mismos gates
siguen corriendo en CI.

**Regla de Oro:** *Después de escribir o editar cualquier archivo, corré su formateador y `format:check` antes de commitear; ningún archivo nuevo llega al commit sin pasar por Prettier o Ruff.*
