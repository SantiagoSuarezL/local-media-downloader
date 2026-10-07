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

### Regla de Oro 6.1 [Tests / SSE]: nunca testear streams infinitos con TestClient

**Error:** el test de `GET /api/v1/events` con `client.stream()` + `iter_lines()` colgó la suite (timeout 60-180 s). El POST creaba el job bien (201); el GET nunca entregó ni una línea.

**Root Cause:** starlette 1.7 `_TestClientTransport.handle_request` corre la app a completitud acumulando el body en un `BytesIO` — no hay streaming real. Un endpoint SSE infinito nunca termina, así que `iter_lines()` bloquea para siempre. No es un bug de nuestro endpoint; es el harness.

**Solución:** el generador SSE vive a nivel módulo (`_event_stream(bus)` en `app.py`; el endpoint es wrapper fino) y los tests lo consumen directo con `asyncio.run` (tomar N frames + `aclose()`). El nivel HTTP se cubre solo con aserción de registro de ruta. `test_events.py` fija además el contrato del bus (replay, historia acotada, drop sin backpressure).

**Regla de Oro:** *Streams infinitos (SSE) se testean consumiendo el generador ASGI directo, jamás vía TestClient; si un test de red cuelga, sospechá primero del harness antes que del código.*

### Regla de Oro 7.1 [Herramientas / PowerShell]: no usar Set-Content/Get-Content para editar archivos UTF-8 con acentos/backticks

**Error:** al archivar Sesión 6 vía `Set-Content`, PowerShell reinterpretó la codificación y los acentos quedaron como `?`/�, y los backticks (`` ` ``) que rodeaban identificadores de código en el markdown fueron evaluados como escapes (se perdieron las comillas invertidas y el texto quedó alterado).

**Root Cause:** PowerShell 5.1 lee/escribe con el code page de la consola por defecto y trata el backtick como carácter de escape dentro de strings expandibles; el archivo resultado quedó corrupto hasta reescribirlo con `[System.IO.File]::ReadAllLines/WriteAllLines` + `UTF8Encoding($false)`.

**Solución:** editar con las herramientas de edición de archivos (edit/write), o si es imprescindible PowerShell, usar `[System.IO.File]::ReadAllLines/WriteAllLines(..., UTF8Encoding($false))` y nunca interpolar markdown con backticks en strings expandibles (`"..."`) — usar comillas simples o single-quoted here-strings.

**Regla de Oro:** *Para modificar archivos del repo con contenido español/markdown, usá edit tools; si usás PowerShell, forzá UTF8 sin BOM con System.IO.File y evitá strings expandibles con backticks.*

### Regla de Oro 8.1 [Git / .gitignore]: anclar a raíz los patrones de directorio heredados

**Error:** `apps/web/src/lib/` (api.ts, live.ts, format.ts, JobCard.svelte — código fuente de Fase 8) era invisible para git: `git check-ignore` reveló que el patrón `lib/` de la plantilla Python lo tragaba en silencio. El mismo riesgo existía para `build/`, `var/`, `target/`, `dist/`, `tmp/`, `temp/`, `cover/`, `coverage/`.

**Root Cause:** los patrones de directorio sin `/` inicial en `.gitignore` aplican en CUALQUIER nivel del árbol, no solo en raíz. Una plantilla Python no sabe que el repo tendrá un `src/lib/` de TypeScript.

**Solución:** anclar a raíz con `/` todos los patrones de directorio de la plantilla (`/lib/`, `/build/`, `/var/`, etc.); `apps/web/dist/` y `apps/extension/dist/` siguen ignorados por sus líneas explícitas de la sección del proyecto. Verificado con `git check-ignore` + `git status`.

**Regla de Oro:** *Todo patrón de directorio en `.gitignore` que venga de una plantilla se ancla a raíz (`/nombre/`); después de tocar el `.gitignore`, verificá con `git check-ignore` los paths de código real antes de darlo por cerrado.*

### Regla de Oro 8.2 [API / Web]: el fallback SPA jamás responde rutas `/api/*`

**Error:** al montar la UI (`/{path:path}` → `index.html`), `GET /api/v1/nope` pasó a devolver 200 HTML en vez del 404 JSON estructurado — cualquier cliente que parseara la respuesta como JSON rompería.

**Root Cause:** la ruta catch-all se registra después de las rutas `/api/v1` reales, pero las rutas API *inexistentes* no tienen con qué matchear y caen al fallback. Servir el shell HTML ahí es un cambio silencioso de contrato.

**Solución:** el fallback excluye explícitamente `api` y `api/*` (404 JSON con `NOT_FOUND`); el banner del servicio se movió de `GET /` a `GET /api/v1` para que la `/` pertenezca siempre al SPA sin condicionales.

**Regla de Oro:** *Si servís un SPA con fallback catch-all, excluí el prefijo de la API por código y testeá que una ruta API desconocida siga siendo 404 estructurado; una API que a veces devuelve HTML es un bug de contrato.*

### Regla de Oro 9.1 [Extensión / permisos]: los host_permissions MV3 son solo loopback, sin IPv6 literal

**Error:** el manifest declaraba `host_permissions: ["http://127.0.0.1/*", "http://localhost/*", "http://[::1]/*"]` para cubrir el servicio en cualquier loopback.

**Root Cause:** los match patterns de Chrome no documentan ni aceptan IPv6 literal como host (documentan `localhost` y `127.0.0.1`); un host inválido hace que Chrome rechace el manifest completo y la extensión no cargue. El patrón `localhost/*` ya cubre el caso `::1` a nivel de resolución de nombres, así que el patrón extra no aportaba nada.

**Solución:** `host_permissions` quedó en `["http://127.0.0.1/*", "http://localhost/*"]` y `tests/manifest.test.ts` falla si alguna vez se agrega un host fuera de loopback. La validación loopback del lado TS (`normalizeServiceUrl`) es independiente y sigue aceptando `::1` para Firefox, donde ese patrón sí es válido.

**Regla de Oro:** *En una extensión que sólo habla con el servicio local, `host_permissions` se limita a `http://127.0.0.1/*` y `http://localhost/*` (nunca `<all_urls>`, nunca IPv6 literal) y esa lista se fija con un test; el least privilege se verifica, no se documenta.*
