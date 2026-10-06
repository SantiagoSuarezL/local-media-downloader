# Lessons Learned — ARCHIVO — local-media-downloader

> Reglas verbatim de fases rotadas. No se lee automático.
> Se consulta solo bajo demanda (grep por número de regla o palabra clave)
> cuando una tarea actual toca un módulo de una fase vieja.
> El índice de qué reglas viven acá está en `lessons_learned.md` (memoria activa).

## Archivo de reglas

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

### Regla de Oro 1.4 [Rendimiento]: el playbook de índices cloud no se transfiere; medir antes de aceptar o rechazar

**Error:** el usuario mencionó un proyecto previo donde una decisión de indexado costó 500M de reads y agotó el límite gratuito mensual de su base de datos serverless. Propuso seis prácticas: índices obligatorios más `EXPLAIN QUERY PLAN`, caché de endpoints con `s-maxage` y Redis, batching, paginación por cursor en vez de `OFFSET`, connection pooling con PgBouncer, y rate limiting con Upstash. El impulso natural es aplicarlas las seis.

**Root Cause:** ese incidente era Postgres serverless, donde cada read se factura. Esta app es un monolito local que liga sólo a loopback: **no hay metering, no hay CDN, no hay serverless, no hay Redis**. Aplicar las reglas sin traducir el modelo de costos habría causado daño real — cuatro de las seis son activamente dañinas o irrelevantes acá. Y al medir, las prácticas 1 y 4 escondían un bug que leer el código no había revelado.

**Solución** (todo medido con `EXPLAIN QUERY PLAN` + timing, no de opinión):
- *Se aplican*: `idx_jobs_sort(priority DESC, created_at DESC, id DESC)` — quita el TEMP B-TREE de `list_jobs`, página superficial 26.10 ms → **0.18 ms** (145x), profunda 12.92 → 5.86 ms, a costa de 3.7 → 4.0 µs/fila en transiciones (+8%). Y paginación por cursor con `id` como desempate único: `created_at` tiene resolución de milisegundos, así que sin desempate el keyset saltaba o duplicaba filas (bug real, ahora cubierto por tests que fuerzan colisiones).
- *Se rechazan con motivo*: caché de endpoints (rompería el estado en vivo que SSE promete; Redis prohibido por principio #33), connection pooling (PgBouncer es para Postgres serverless; aquí hay un worker y una conexión), rate limiting con Redis (el riesgo real es una web local pegándole a la API, que se resuelve con Origin validation + token en Fase 10), e índices indiscriminados (se probaron dos y se descartaron: no quitaron el temp b-tree y costaron **3x** en escrituras, 10.2 vs 3.5 µs/fila).
- Costo real del escaneo total para contexto: 5k jobs 1.0 ms · 50k 11 ms · 200k 44 ms. Un full scan aquí es barato; el problema nunca fue el scan, fue el **sort**.

**Regla de Oro:** *Cada regla de un playbook cloud se evalúa contra el modelo de costos de ESTE proyecto antes de aplicarse: indexar sólo lo que un `EXPLAIN QUERY PLAN` + medición demuestren, y rechazar con motivo escrito lo que no aplique. "SCAN TABLE" no es un bug por sí mismo; "TEMP B-TREE FOR ORDER BY" en una consulta paginada sí lo es.*
