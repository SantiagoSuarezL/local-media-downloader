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

---

## Reglas activas

### Regla de Oro 17.1 [Adapters / errores]: el texto DNS de un fallo cambia con la plataforma — matcheá la causa, no el wrapper

**Error:** CI rojo desde Fase 13 sin que nadie lo mirara (Sesión 27): el smoke fallaba SOLO en `backend ubuntu-latest` — `POST /api/v1/resolve` con URL `.invalid` devolvía 503 TOOL_OUTDATED cuando el test exige {502, 504}. En Windows pasaba.

**Root Cause:** glibc dice "Name or service not known" (urllib3: "Failed to resolve") y Winsock dice "getaddrinfo failed". `_NETWORK` solo conocía la variante Windows, así que en Linux la línea `Unable to download webpage: ... Name or service not known` caía en `_BROKEN_EXTRACTOR` → TOOL_OUTDATED. Mismo host, distinto ErrorCode según el OS.

**Solución (Sesión 27):** `_NETWORK` suma `name or service not known|failed to resolve|name resolution` (la regla ya estaba antes que `_BROKEN_EXTRACTOR`, el orden no se tocó) + 2 filas de regresión en `test_adapter_errors.py` con stderr estilo glibc que también contiene "Unable to download webpage" (prueban que la causa específica gana por orden).

**Regla de Oro:** *Si clasificás stderr de una herramienta externa por regex, cada causa necesita sus variantes por plataforma (glibc vs Winsock como mínimo); y el test de regresión debe incluir la línea wrapper completa para probar que la causa específica gana por orden de reglas.*

### Regla de Oro 14.2 [Planner / Executor]: un flag que la estrategia elegida no puede ejecutar no se propaga — fuerza la estrategia o se rechaza

**Error:** el slice audio normalization (Sesión 19) propagaba `audio_normalize` como detalle a TODOS los plan steps, incluidos REMUX (`-c copy`) y VIDEO_ONLY (sin pista de audio). Con una fuente copy-compatible (el caso común mp4→mp4) el plan elegía strategy "copy" y la normalización nunca se aplicaba. Además el executor pasaba `audio_normalize=` incondicionalmente a `transcode`, y cualquier procesador con firma de Fase 4 (compatibilidad documentada, Regla 14.1) reventaba con TypeError — enmascarado agregando `**kwargs` al stub `_LegacyTranscoder` del test viejo.

**Root Cause:** el flag se modeló como metadata del plan ("poné la key en todos los steps") en vez de como una restricción de estrategia (loudnorm es un filtro: re-encode obligatorio → pertenece a la condición `compatible`, igual que trim/resize/crop/encode). Y al extender la llamada a `transcode`, el único guardián de compatibilidad (`_supports_encode_options`) sólo se evaluaba con bitrate/framerate presentes: el kwarg nuevo quedó fuera de la verificación y el test legacy se "arregló" perdiendo su propósito.

**Solución (Sesión 20):** `audio_normalize` entra al check `compatible` del plan full-video (fuerza TRANSCODE); se rechaza con UNSUPPORTED_INTENT para `audio=remove` y presets; fuera de los steps de stream copy (un detalle muerto promete algo que el step no hace). El executor reenvía el kwarg sólo si fue pedido y el procesador lo declara (`_supports_audio_normalize`, inspección de firma como Regla 14.1); pedido-pero-no-soportado → UNSUPPORTED_INTENT. `_LegacyTranscoder` restaurado a su firma original y la feature blindada con su matriz de capability (`test_audio_normalize.py`, §528).

**Regla de Oro:** *Una capability nueva que una estrategia del plan no puede aplicar nunca viaja como detalle muerto: o fuerza la estrategia que la aplica (check `compatible` del planner) o se rechaza antes de ejecutar. Y al extender lo que el executor pasa a un método ya existente de un puerto, el reenvío es condicional a la firma real — jamás se afloja un stub viejo para absorber el kwarg nuevo (ese test es precisamente el guardian de la compatibilidad).*

### Regla de Oro 14.1 [Python / Protocolos]: un protocolo runtime_checkable que redeclara un método existente no detecta nada

**Error:** el slice encode-options de Fase 14 definió `VideoEncodeOptionsTool` — protocolo `runtime_checkable` cuyo único miembro es `transcode`, nombre que `MediaTool` ya declara. Pyright falló dos veces: "Class overlaps ... unsafely and could produce a match at runtime" sobre el `isinstance`, y el unpack `**_EncodeKwargs` no matcheaba parámetros porque en la intersección `MediaTool & VideoEncodeOptionsTool` la llamada se resuelve contra la firma de `MediaTool`.

**Root Cause:** `isinstance` contra un protocolo `runtime_checkable` sólo verifica *presencia* de miembros, jamás firmas. Como todo `MediaTool` tiene `transcode` (los stubs de la Fase 4 incluidos), el guardián daba `True` para procesadores que rechazarían los kwargs con `TypeError` en runtime — pyright señalaba un bug latente, no ruido de tipeo. `TrimTool`/`ResizeTool`/`CropTool` funcionan porque sus nombres (`transcode_trimmed`, `resize`, `crop`) no existen en `MediaTool`: ahí presencia sí prueba capacidad.

**Solución:** la capacidad se verifica desde la firma real (`_supports_encode_options` con `inspect.signature(processor.transcode).parameters`) y la llamada se hace vía `cast(VideoEncodeOptionsTool, ...)`; el protocolo dejó de ser `runtime_checkable` y su docstring documenta por qué.

**Regla de Oro:** *Para detectar en runtime una extensión de firma de un método que ya existe en el protocolo base, nunca uses `isinstance` runtime_checkable (presencia no prueba firma, y pyright lo marca como overlap inseguro): inspeccioná `inspect.signature` o dale a la capacidad un nombre de método propio.*
