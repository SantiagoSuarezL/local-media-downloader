# Lessons Learned — local-media-downloader

> MEMORIA ACTIVA. Se lee completa al inicio de sesión.
> Reglas de fases viejas: ver `lessons_learned_archive.md` (NO se lee
> automático, solo por grep/keyword si la tarea actual toca esa fase).
> Regla de rotación: este archivo debe contener solo las reglas de las
> últimas 2 fases. Al cerrar una fase nueva, la más vieja de las que
> quedan acá pasa al archivo y se reemplaza por una línea de índice abajo.

## Índice de reglas archivadas

- 1.1 [Tooling / uv]: workspace members — ver `lessons_learned_archive.md`.
- 1.2 [Git / reproducibilidad]: lockfiles se versionan — ver `lessons_learned_archive.md`.
- 1.3 [Proceso / formateo]: formatear tras escribir — ver `lessons_learned_archive.md`.
- 1.4 [Rendimiento]: playbook cloud no se transfiere — ver `lessons_learned_archive.md`.
- 6.1 [Tests / SSE]: streams infinitos por generador, nunca TestClient — ver `lessons_learned_archive.md`.
- 7.1 [Herramientas / PowerShell]: no editar UTF-8 con Set-Content — ver `lessons_learned_archive.md`.
- 8.1 [Git / .gitignore]: anclar patrones de directorio a raíz — ver `lessons_learned_archive.md`.
- 8.2 [API / Web]: el fallback SPA no responde `/api/*` — ver `lessons_learned_archive.md`.

---

## Reglas activas

### Regla de Oro 9.1 [Extensión / permisos]: los host_permissions MV3 son solo loopback, sin IPv6 literal

**Error:** el manifest declaraba `host_permissions: ["http://127.0.0.1/*", "http://localhost/*", "http://[::1]/*"]` para cubrir el servicio en cualquier loopback.

**Root Cause:** los match patterns de Chrome no documentan ni aceptan IPv6 literal como host (documentan `localhost` y `127.0.0.1`); un host inválido hace que Chrome rechace el manifest completo y la extensión no cargue. El patrón `localhost/*` ya cubre el caso `::1` a nivel de resolución de nombres, así que el patrón extra no aportaba nada.

**Solución:** `host_permissions` quedó en `["http://127.0.0.1/*", "http://localhost/*"]` y `tests/manifest.test.ts` falla si alguna vez se agrega un host fuera de loopback. La validación loopback del lado TS (`normalizeServiceUrl`) es independiente y sigue aceptando `::1` para Firefox, donde ese patrón sí es válido.

**Regla de Oro:** *En una extensión que sólo habla con el servicio local, `host_permissions` se limita a `http://127.0.0.1/*` y `http://localhost/*` (nunca `<all_urls>`, nunca IPv6 literal) y esa lista se fija con un test; el least privilege se verifica, no se documenta.*

### Regla de Oro 10.1 [API / errores]: todo ErrorCode del dominio tiene estado HTTP, o el 500 miente

**Error:** `error_response()` tenía un mapa de `ErrorCode` → status; `UNSUPPORTED_INTENT`, `VALIDATION_FAILED` y el nuevo `BLOCKED_SOURCE` no estaban, así que caían al default 500. Se vio en Fase 10: un `POST /api/v1/jobs` con intent inválido devolvía 500 "internal error" cuando el problema era del usuario.

**Root Cause:** el mapa se.armó por Taxonomía (Fase 3) y se fue llenando por symptom (Fase 4/5). Cada código nuevo parecía opcional, y el default 500 silenciaba el hueco: nada fallaba en los tests porque los tests existentes nunca ejercitaban esos códigos por HTTP.

**Solución:** los tres códigos se agregaron al mapa (400/422) y hay un test que itera `UNSUPPORTED_INTENT`, `VALIDATION_FAILED` y `BLOCKED_SOURCE` exigiendo 4xx. `BLOCKED_SOURCE` es nuevo en Fase 10 (guarda SSRF).

**Regla de Oro:** *Al agregar un `ErrorCode`, agregalo también a `_STATUS_BY_CODE` en el mismo commit, y mantené un test que exija 4xx para todo error causado por el usuario: el default 500 convierte un error del cliente en "internal error".*

### Regla de Oro 10.2 [Tests / e2e]: un smoke test contra un puerto ocupado valida el servidor viejo

**Error:** el smoke test de Fase 10 dio `jobs-noauth:200` y "token no inyectado" contra `127.0.0.1:8765` — resultados que parecían un agujero de seguridad. No lo eran: un granian de la Sesión 8 seguía escuchando ese puerto y el proceso no se podía matar (`taskkill` decía que no existía, aunque el socket seguía en Listen).

**Root Cause:** el comando de la Sesión 8 lanzó el servidor y el tool lo cortó por timeout, dejando un worker vivo. El smoke test nuevo no verificó que el puerto fuera suyo antes de interpretar las respuestas.

**Solución:** reproducir en otro puerto (`LMD_PORT=8766`) y ahí sí: health 200 público, jobs sin token 401, shell con `<meta lmd-token>`, jobs con header 200, cookie 200 (ruta del EventSource), `Host: evil.example.com` 403, y `LMD_HOST=0.0.0.0` aborta con `Refusing to bind`. Para pruebas locales de API, verificar que el puerto esté libre antes de concluir nada de una respuesta.

**Regla de Oro:** *Antes de interpretar la respuesta de un smoke test e2e, confirmá que el proceso que escucha el puerto es el que acabás de arrancar (puerto libre o puerto alterno): un servidor viejo en 8765 es indistinguishable de un fallo de seguridad.*

### Regla de Oro 10.3 [Tooling / pnpm]: los settings de build scripts de pnpm 10 ya no existen en pnpm 11

**Error:** el job `frontend` de CI venía fallando en ambos OS desde el commit de Fase 3, sin que nadie lo notara: `pnpm install --frozen-lockfile` abortaba con `ERR_PNPM_IGNORED_BUILDS` (deno). En local todo pasaba porque el `node_modules` ya tenía el binario de deno de instalaciones viejas.

**Root Cause:** pnpm 11 (este repo usa `packageManager: pnpm@11.2.2`) **removió** `onlyBuiltDependencies` y lo ignora en silencio; el reemplazo es el mapa `allowBuilds: { deno: true }` en `pnpm-workspace.yaml`. Con `onlyBuiltDependencies`, el postinstall de deno no corría en ninguna máquina limpia — o sea, el runtime JS de yt-dlp-ejs tampoco estaba instalado en CI.

**Solución:** `pnpm-workspace.yaml` usa `allowBuilds: { deno: true }` con comentario que explica la migración; verificado con un clon limpio (`git clone --depth 1` + `rm -rf node_modules` + los 5 pasos del job frontend) antes de pushear. Codemod oficial: `pnpx codemod run pnpm-v10-to-v11`.

**Regla de Oro:** *Un `pnpm install` que pasa en tu máquina no prueba nada si los `node_modules` ya existían: reproducí los pasos de CI en un clon limpio antes de declarar verde cualquier job de JS. Y si cambiás de versión mayor de pnpm, los settings de build scripts se renombran — no se borran en silencio.*
