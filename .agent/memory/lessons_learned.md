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

---

## Reglas activas

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

### Regla de Oro 12.1 [Retention / tiempo]: el mantenimiento nunca toca `updated_at`

**Error:** `clear_source_url` actualizaba `updated_at` al redactar. Como el sweep corre redact-antes-que-borrado en la misma pasada, el job redactado pasaba a verse "recién modificado" y `list_terminal_older_than` ya no lo encontraba: `history_retention_days` nunca borraba nada que antes hubiera sido redactado. Lo cazó `test_retention_deletes_old_history_rows`.

**Root Cause:** `updated_at` tiene dos lectores con semánticas distintas: la UI lo muestra como "última actividad" y retention lo usa como "edad para cleanup". Un write de mantenimiento satisface al primero y ciega al segundo.

**Solución:** `clear_source_url` no toca `updated_at` (documentado en el docstring); la edad de un job terminal la define su última transición de estado, no la última pasada del sweep.

**Regla de Oro:** *Si una columna se usa como reloj de retention, ningún write de mantenimiento puede modificarla: el mantenimiento que rejuvenece lo que limpia se auto-anula.*

### Regla de Oro 12.2 [API / FastAPI]: un endpoint que devuelve `Response` no puede anotar `dict`

**Error:** al agregar ramas de error `JSONResponse` a `GET /api/v1/jobs`, la anotación `-> dict[str, object] | JSONResponse` rompió el registro de rutas: FastAPI intenta construir un response model pydantic de la unión y `create_app()` explota en import (`FastAPIError: Invalid args for response field`), tumbando TODA la suite (4 archivos ni siquiera coleccionan).

**Root Cause:** la anotación de retorno de un path operation no es solo typing: FastAPI la usa para generar el response model, y `Response` no es un field pydantic válido.

**Solución:** `response_model=None` en el decorador cuando el endpoint puede devolver una `Response` cruda; pyright sigue verificando la unión en el cuerpo.

**Regla de Oro:** *Si un endpoint devuelve `JSONResponse` en alguna rama, poné `response_model=None` en el decorador: sin eso, un cambio de anotación tumba el import de la app entera.*
