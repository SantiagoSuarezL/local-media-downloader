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

---

## Reglas activas

### Regla de Oro 6.1 [Tests / SSE]: nunca testear streams infinitos con TestClient

**Error:** el test de `GET /api/v1/events` con `client.stream()` + `iter_lines()` colgó la suite (timeout 60-180 s). El POST creaba el job bien (201); el GET nunca entregó ni una línea.

**Root Cause:** starlette 1.7 `_TestClientTransport.handle_request` corre la app a completitud acumulando el body en un `BytesIO` — no hay streaming real. Un endpoint SSE infinito nunca termina, así que `iter_lines()` bloquea para siempre. No es un bug de nuestro endpoint; es el harness.

**Solución:** el generador SSE vive a nivel módulo (`_event_stream(bus)` en `app.py`; el endpoint es wrapper fino) y los tests lo consumen directo con `asyncio.run` (tomar N frames + `aclose()`). El nivel HTTP se cubre solo con aserción de registro de ruta. `test_events.py` fija además el contrato del bus (replay, historia acotada, drop sin backpressure).

**Regla de Oro:** *Streams infinitos (SSE) se testean consumiendo el generador ASGI directo, jamás vía TestClient; si un test de red cuelga, sospechá primero del harness antes que del código.*
