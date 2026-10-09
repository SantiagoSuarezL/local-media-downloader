# Lessons Learned — local-media-downloader

> MEMORIA ACTIVA. Se lee completa al inicio de sesión.
> Reglas de fases viejas: ver `lessons_learned_archive.md` (NO se lee
> automático, solo por grep/keyword si la tarea actual toca esa fase).
> Regla de rotación: este archivo debe contener solo las reglas de las
> últimas 2 fases. Al cerrar una fase nueva, la más vieja de las que
> quedan acá pasa al archivo y se reemplaza por una línea de índice abajo.

## Índice de reglas archivadas

- 10.1 [API / errores]: todo ErrorCode tiene estado HTTP — ver `lessons_learned_archive.md`.
- 10.2 [Tests / e2e]: probar que el puerto es tuyo antes de interpretar respuestas — ver `lessons_learned_archive.md`.
- 10.3 [Tooling / pnpm]: los settings de build scripts se renombran entre versiones mayores — ver `lessons_learned_archive.md`.
- 9.1 [Extensión / permisos]: host_permissions MV3 solo loopback — ver `lessons_learned_archive.md`.
- 1.1 [Tooling / uv]: workspace members — ver `lessons_learned_archive.md`.
- 1.2 [Git / reproducibilidad]: lockfiles se versionan — ver `lessons_learned_archive.md`.
- 1.3 [Proceso / formateo]: formatear tras escribir — ver `lessons_learned_archive.md`.
- 1.4 [Rendimiento]: playbook cloud no se transfiere — ver `lessons_learned_archive.md`.
- 6.1 [Tests / SSE]: streams infinitos por generador, nunca TestClient — ver `lessons_learned_archive.md`.
- 7.1 [Herramientas / PowerShell]: no editar UTF-8 con Set-Content — ver `lessons_learned_archive.md`.
- 8.1 [Git / .gitignore]: anclar patrones de directorio a raíz — ver `lessons_learned_archive.md`.
- 8.2 [API / Web]: el fallback SPA no responde `/api/*` — ver `lessons_learned_archive.md`.
- 12.1 [Retention / tiempo]: el mantenimiento nunca toca `updated_at` — ver `lessons_learned_archive.md`.
- 12.2 [API / FastAPI]: un endpoint que devuelve `Response` no puede anotar `dict` — ver `lessons_learned_archive.md`.
- 14.1 [Python / Protocolos]: presence de miembro no prueba firma (runtime_checkable) — ver `lessons_learned_archive.md`.
- 14.2 [Planner / Executor]: una capability que la estrategia no puede aplicar no viaja como detalle muerto — ver `lessons_learned_archive.md`.

---

## Reglas activas

### Regla de Oro 17.6 [Diagnostics / herramientas]: el detector y el adapter resuelven binarios con la MISMA función

**Error (Sesión 33, reporte del usuario):** la pestaña Diagnostics mostraba `deno: no` y `yt_dlp_ejs: no` mientras el servicio funcionaba: `detect_tools` probaba `"ffmpeg"`/`"deno"`/... por `PATH`, pero el runtime nunca usa el PATH (Deno se resuelve en `node_modules/.bin` vía `find_deno()`, ffmpeg en el venv). El reporte describía una máquina que no era la que corría los procesos.

**Root Cause:** la resolución se implementó dos veces con criterios distintos. `adapters/tool_paths.py` (override → bundle → node_modules → venv → PATH) es la fuente de verdad, pero `diagnostics.py` la esquivó con nombres de ejecutable sueltos — el invariante de "no depender del PATH global" quedó escrito en `tech_stack.md` pero nunca se aplicó al detector. Además el probe de EJS leía `__version__`, atributo que el paquete no expone (es `version`), así que un EJS instalado se reportaba ausente igual.

**Solución:** `detect_tools` compone sus argv con `yt_dlp_argv()`/`find_deno()`/`ffmpeg_argv()`/`ffprobe_argv()` (los mismos del adapter) y `_ejs_version()` acepta ambas grafías; se sigue reportando solo la primera línea de salida para no filtrar paths (health es reachable sin token). `tests/test_diagnostics.py` (11 tests) fija que el argv del probe ES el argv del adapter, que Deno fuera del PATH igual se detecta, y que timeout/ausencia se reportan `detected: false`.

**Regla de Oro:** *Un diagnóstico que resuelve herramientas por su cuenta describe un entorno que no existe: el probe tiene que componerse con la misma función de resolución que usa el runtime (test que lo fije), y "detected" significa "lo va a ejecutar", no "lo encuentro en el PATH".*

### Regla de Oro 17.5 [Adapters / CLI]: el prefijo de tipo de un `--progress-template` lo consume la herramienta, y el test que arma la línea a mano valida la suposición

**Error (Sesión 33, reporte del usuario):** Downloaded / Speed / ETA siempre `—` y la barra en vivo nunca se movía (solo saltaba 0→100% al completar, desde el valor persistido en DB). El parser exigía líneas con prefijo `download:lmd\x1f`; el `TEMPLATE` de `adapters/progress.py` empezaba con `"download:"`, pero en `--progress-template` ese `download:` es la CLAVE del tipo de salida (`progress_template["download"]`) y yt-dlp la consume: lo que se imprime empieza en `lmd\x1f`. Toda línea de progreso se descartaba en silencio (`parse_progress_line` devuelve `None` y el loop sigue).

**Root Cause:** el test construía la línea con `_line()` replicando la suposición equivocada, así que la suite entera pasaba con el protocolo roto (mismo patrón que 17.1/17.2: el test fijaba la implementación, no el contrato con la herramienta). El parser era correcto; el que mentía era el template.

**Solución:** el template ya no lleva prefijo de tipo (ni el `\n` final, que `--newline` ya pone) y `parse_progress_line` matchea `RECORD_PREFIX`. El contrato nuevo se verifica con las piezas reales de yt-dlp: `parse_options([...])` devuelve `progress_template["download"]` (prueba de que el prefijo se consume) y `YoutubeDL.evaluate_outtmpl` renderiza la línea como lo hace `_report_progress_status` (incluido el `NA` de los campos ausentes) — `test_rendered_record_from_ytdlp_option_parsing_parses`. Verificado end-to-end contra la herramienta real: 0 registros antes, 15 con bytes/velocidad/ETA después.

**Regla de Oro:** *Cuando el protocolo de progreso lo produce una herramienta externa, el test tiene que producir la línea con la herramienta (su parser de opciones y su renderer de templates), no con un f-string que replica lo que creemos que imprime: un test que arma la línea a mano valida la suposición, no el contrato.*

### Regla de Oro 17.4 [Servicio / shutdown]: un stream infinito más kill-timeout deshabilitado = Ctrl+C que no para

**Error (Sesión 32, test usuario):** Ctrl+C sobre el backend imprimía `[INFO] Stopping worker-1` y la terminal nunca devolvía el prompt mientras el dashboard estuviera abierto.

**Root Cause:** `/api/v1/events` es un SSE que espera `queue.get()` para siempre → una pestaña abierta del dashboard deja a ese task in-flight indefinidamente. Granian con `workers_kill_timeout=None` (el default) espera al worker SIN límite: el graceful shutdown nunca termina de matar al worker.

**Solución:** `workers_kill_timeout=1` en la llamada a `Granian` en `__main__.py` (1 s de grace, luego kill del worker). Ojo: en Windows un Ctrl+C real no se replica fácil en tests automáticos — los eventos de consola no viajan por pipes (`send_signal(SIGINT)` falla salvo `CTRL_C_EVENT` con `CREATE_NEW_PROCESS_GROUP`), así que la verificación de este fix vive en el test manual del Ctrl+C del usuario.

**Regla de Oro:** *Todo servidor con streams infinitos (SSE/WebSocket) configura su kill-timeout explícito en el mismo commit que introduce el stream — el default "disabled" de Granian convierte un Ctrl+C en un hang si hay vivo cualquier cliente con stream abierto.*

### Regla de Oro 17.3 [Adapters / compat]: un archivo válido con sub-frames voltea al demuxer viejo — CI usa binarios de la clase pineada

**Error:** instalar ffmpeg en CI ubuntu destapó `sticker-webp` en rojo: ffprobe 0x0 + `Decode error rate 1 exceeds maximum` sobre un archivo VÁLIDO (canvas VP8X 512x512, 10 KB, gyan 9.0.1 lo lee perfecto).

**Root Cause:** libwebp recorta cada frame al bbox no-transparente y emite ANMF sub-frames con offset (nuestro pad transparente lo provoca siempre). El demuxer/decoder nativo ≤8.x no tolera esos sub-frames (dims 0, decode EINVAL en todos los frames); 9.x sí. Ni apt ni johnvansickle-7.0.2 servían (este último, además, sin libsvtav1 para el test AV1).

**Solución (Sesión 29):** CI ubuntu+windows con BtbN n9.0 static pineado (misma clase que el bundle 9.0.1) → 547 passed en ambos OS; más robustez real: dims 0→None en el parse (el contrato probe.py dice que ausencia es None), fallback a coded dims, y `validate()` rellena dims desconocidas desde frames decodeados (showinfo, fail closed) para usuarios con ffmpeg viejo.

**Regla de Oro:** *Si el producto emite un formato con features que los demuxers viejos no leen, CI corre con binarios de la misma clase que los pineados en el bundle — un apt de 2 años vuelve rojo un archivo válido. Y dimensión 0 del probe es ausencia (None), nunca un tamaño.*

### Regla de Oro 17.2 [Web / Dev]: el proxy dev debe presentar el Host del backend, no el de Vite

**Error:** con `pnpm dev` (:5173) + backend (:8765), el dashboard daba 403 `INVALID_HOST` en `/api/v1/jobs` y `/api/v1/events`. En producción (:8765 sirviendo el build) funcionaba.

**Root Cause:** el proxy de Vite tenía `changeOrigin: false`, así que el backend recibía `Host: 127.0.0.1:5173` y `validate_host(expected_port=8765)` lo rechazaba por puerto. El comentario del proxy ("same origin, no allowance needed") describía la intención pero el flag hacía exactamente lo contrario.

**Solución (Sesión 28):** `changeOrigin: true` en `apps/web/vite.config.ts` + comentario que cita el check. El `Origin: http://127.0.0.1:5173` que el browser sí manda pasa `validate_origin` (solo exige host loopback, no puerto). Nota: en dev el token igual viene por cookie (hay que abrir :8765 una vez para que FastAPI la fije; las cookies ignoran el puerto).

**Regla de Oro:** *Si el backend valida el puerto del `Host`, el proxy dev lleva `changeOrigin: true` sí o sí — con `false` el backend ve el puerto de Vite y todo `/api/*` da 403. Y el comentario del proxy debe nombrar el check que lo exige, no solo la intención.*

### Regla de Oro 17.1 [Adapters / errores]: el texto DNS de un fallo cambia con la plataforma — matcheá la causa, no el wrapper

**Error:** CI rojo desde Fase 13 sin que nadie lo mirara (Sesión 27): el smoke fallaba SOLO en `backend ubuntu-latest` — `POST /api/v1/resolve` con URL `.invalid` devolvía 503 TOOL_OUTDATED cuando el test exige {502, 504}. En Windows pasaba.

**Root Cause:** glibc dice "Name or service not known" (urllib3: "Failed to resolve") y Winsock dice "getaddrinfo failed". `_NETWORK` solo conocía la variante Windows, así que en Linux la línea `Unable to download webpage: ... Name or service not known` caía en `_BROKEN_EXTRACTOR` → TOOL_OUTDATED. Mismo host, distinto ErrorCode según el OS.

**Solución (Sesión 27):** `_NETWORK` suma `name or service not known|failed to resolve|name resolution` (la regla ya estaba antes que `_BROKEN_EXTRACTOR`, el orden no se tocó) + 2 filas de regresión en `test_adapter_errors.py` con stderr estilo glibc que también contiene "Unable to download webpage" (prueban que la causa específica gana por orden).

**Regla de Oro:** *Si clasificás stderr de una herramienta externa por regex, cada causa necesita sus variantes por plataforma (glibc vs Winsock como mínimo); y el test de regresión debe incluir la línea wrapper completa para probar que la causa específica gana por orden de reglas.*
