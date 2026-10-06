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

`Sesión 10 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)`

- Fase 10 (Security hardening) — nuevo `security.py`: token de instalación persistido en la tabla `settings` (`secrets.token_urlsafe`, comparación con `compare_digest`, registrado como secreto para redacción), validación de `Host`/`Origin` strictly-loopback (anti DNS-rebinding), y `assert_loopback_host` que aborta el arranque con `LMD_HOST=0.0.0.0` (verificado e2e).
- Middleware `security_boundary` en `app.py`: Host/Origin → 403, `Content-Length` > 64 KiB (`LMD_MAX_REQUEST_BYTES`) → 413, y token obligatorio en todo `/api/*` salvo `/api/v1` y `/api/v1/health` (públicos porque la extensión solo puede hacer health). El token llega al dashboard por `<meta name="lmd-token">` + cookie `HttpOnly`/`SameSite=Strict` inyectados en el shell (ya validado contra Host), y la SPA lo manda por header; el SSE se autentica con la cookie porque EventSource no setea headers.
- `domain/urls.py`: se rechazan credenciales embebidas (`user:pass@`) y hosts loopback/privados/link-local/metadata (`127.0.0.1`, `localhost`, `192.168.*`, `169.254.169.254`, `.local`, `[::1]`) con el nuevo `ErrorCode.BLOCKED_SOURCE` → **se revierte** la decisión de Fase 1 de permitir loopback como origen, porque convertía la app en proxy SSRF a la LAN.
- `domain/filenames.py`: `sanitize_filename` (strip de separadores/caracteres Windows, reservados `CON`/`COM1`…, NUL, trim, tope 120 chars) + `output_path_for` que **prueba** contención en el output dir del job; el executor ya no arma la ruta con el título crudo.
- `services/rate_limit.py` (token bucket) aplicado a `POST /api/v1/resolve` (30/min, `LMD_RESOLVE_RATE_LIMIT`) con `Retry-After`; el health público cachea 5 s porque su detección de tools lanza subprocesses (DoS local).
- `logging_config`: `register_secret` + redacción de secretos en mensaje y extras.
- Bugs encontrados: (1) `_STATUS_BY_CODE` sin `UNSUPPORTED_INTENT`/`VALIDATION_FAILED`/`BLOCKED_SOURCE` devolvía 500 a errores del usuario (Regla 10.1); (2) bug propio: `_host_of` recibía `//host` y le anteponía otro esquema → todos los requests 403 (caído por tests); (3) `Origin: null` se aceptaba y ahora se rechaza; (4) `asyncio.run()` sobre un `asyncio.Lock` creado en el lifespan → el endpoint resolve pasó a `async` con `asyncio.to_thread` para el subprocess.
- `tests/conftest.py` con `serving()`: los tests usan `Host` loopback y token real, igual que el dashboard. `test_security.py`: 53 tests (bind, DNS rebinding, cross-origin, token/cookie/persistencia, no-log del token, 413, 422 URL larga, rate limit 429, `file://`/`../../`/`data:`/`javascript:`/`127.0.0.1`/comandos, filenames + contención, `shell=True` ausente).
- Gates: pytest 246 passed / 3 live skipped, pyright 0, ruff clean, svelte-check 0, eslint+prettier clean, vitest 22, builds web+extension ok. E2E verificado contra servidor real en `:8766` (el `:8765` quedó tomado por un worker huérfano de la Sesión 8 → Regla 10.2).
- Commit `8666100` (fases 7–10) pusheado a main; `gh` CLI instalado vía scoop (2.102.0) y CI consultado por la API pública de GitHub: **`frontend` venía en rojo desde el commit de Fase 3** mientras `backend` pasaba en ambos OS. Causa: pnpm 11 remueve `onlyBuiltDependencies` (ignorada en silencio) y el install limpio moría con `ERR_PNPM_IGNORED_BUILDS` (deno nunca corría su postinstall → tampoco estaba el runtime JS de yt-dlp-ejs). Fix: `allowBuilds: { deno: true }`, verificado en un clon limpio con los 5 pasos del job frontend (Regla 10.3).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 9 — 2026-10-06` — Fase 9: extensión MV3, handoff `?url=`, health Connected/Offline; Regla 9.1 (host_permissions solo loopback).
- `Sesión 8 — 2026-10-06` — Fase 8: UI Svelte 5 servida por FastAPI; Reglas 8.1 y 8.2.
- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
