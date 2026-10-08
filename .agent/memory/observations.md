# Observaciones — local-media-downloader

> 5to archivo del protocolo, explícito (no un archivo suelto). Solo
> observaciones EN CURSO (no resueltas todavía, requieren más monitoreo).
> Una vez que una observación se convierte en regla de código confirmada,
> se archiva en `observations_archive.md` y queda solo una línea de cierre
> acá apuntando a la Regla de Oro correspondiente en `lessons_learned.md`.

Formato de cada entrada: fecha, target/módulo, observación, hipótesis, estado, acción.

## En curso

- **2026-10-08 — Smoke del bundle frozen pendiente (Fase 16 sigue abierta).**
  Target `apps/api/lmd.spec` + `lmd_entry.py` + `packaging/stage_bundle.ps1`.
  El spec portable compila (PyInstaller 6.22.3 onedir OK, 2 builds); el primer
  boot frozen falló por imports relativos (`__main__.py` top-level → shim
  `lmd_entry.py`); el segundo intento se colgó en el smoke y dejó 5 `ffmpeg`
  zombie (tool probes del health) → matados, `dist/`+`build/` eliminados por
  presión de RAM. Sin reintentar por decisión del usuario: commitear liviano.
  *Estado:* abierto — reintentar con recursos libres: boot del exe + `/` sirve
  `index.html` (prueba `default_web_dist` frozen) + `/api/v1/health` con
  binarios de `bin/` + checklist browser real de la entrada 2026-10-06.
  *Acción:* ninguna todavía; no bloquear el commit del groundwork por esto.

- **2026-10-08 — Primer `/health` tarda ~12.5 s por los tool probes en frío.**
  Target `app.py`/`diagnostics.py` (`detect_tools` en el path de health).
  Boot→listen 0.56–1.64 s pero →first 200 10–22 s: el delta son los probes
  (cada uno spawnea yt-dlp como módulo python + ffmpeg + deno en frío,
  más Defender en Windows). Los siguientes health: med 3 ms / p95 17 ms.
  *Hipótesis:* con binarios bundled y pineados (Fase 16) el frío baja solo;
  si no, evaluar cachear/diferir detección sin cambiar la semántica del
  contrato (el health debe reportar estado vivo de herramientas).
  *Estado:* abierto — re-medir al cerrar Fase 16 con el bundle instalado.
  *Acción:* ninguna todavía; si se toca, lleva test (contrato de health).

- **2026-10-08 — Download throughput sin baseline: crear jobs exige red.**
  Target `adapters/yt_dlp.py` + `POST /api/v1/jobs` (resuelve síncrono vía
  yt-dlp real; `.invalid`→502 por diseño). Sin red no se puede crear ningún
  job por HTTP real, así que throughput de descarga y cola sobre HTTP real
  no tienen baseline hermético (cola in-process: pickup med 13.3 ms).
  *Hipótesis:* ninguna anomalía esperada (límites scheduler 3/2/1 con
  headroom), pero sin número no hay tuning fundado de fragment concurrency.
  *Estado:* abierto — medir con `LMD_LIVE_NETWORK=1` contra medios públicos
  de test al cerrar Fase 16/17 (TESTING.md §5: live-network siempre opt-in).
  *Acción:* ninguna todavía; no bloquear Fase 16 por esto.

- **2026-10-07 — Batch de 100 URLs largas podría superar el límite de 64 KiB.**
  `POST /api/v1/jobs/batch` acepta hasta 100 items (`BatchRequest`, `max_length=100`)
  pero el middleware rechaza bodies > 64 KiB (`LMD_MAX_REQUEST_BYTES`) con 413.
  100 URLs de longitud máxima (2048) + intents ≈ 225 KB: un batch legítimo pero
  extremo sería rechazado. Con URLs reales (~40-100 chars) un batch lleno pesa
  ~25-30 KB y pasa sin problema, así que hoy no se toca el límite.
  *Hipótesis:* el riesgo crece si los intents engordan (Fase 13 presets, Fase 14
  processing con trim/crop/resize) o si alguien pega URLs larguísimas.
  *Estado:* abierto — monitorear al cerrar Fase 13/14: si un preset nuevo hace
  que el batch típico se acerque a 64 KiB, subir el límite o paginar el submit
  del dashboard es la corrección (y lleva test en `test_smoke_e2e.py`).
  Nota Sesión 18 (slice encode-options Fase 14): los intents crecieron 2 keys
  opcionales (`video_bitrate`/`video_framerate`, ~50 B solo cuando se usan) —
  el batch típico sigue lejos del límite; re-chequear al cerrar Fase 14.
   Nota Sesión 20 (slice audio normalization Fase 14): +1 key opcional
   (`audio_normalize`, ~25 B solo cuando se usa) — sin impacto; re-chequeo sigue
   pautado al cerrar Fase 14.
   Nota Sesión 21 (cierre Fase 14): +2 keys opcionales (`subtitles`/`metadata`,
   ~35 B solo cuando se usan) — sin impacto; el batch típico sigue lejos del
   límite al cerrar la fase. La observación sigue abierta (los intents pueden
   seguir creciendo en futuras fases).
  *Acción:* ninguna todavía; la sonda 413 del smoke ya cubre el comportamiento
  actual (va última y con cliente fresco: el 413 se responde sin consumir el
  body y reutilizar ese keep-alive envenena la siguiente petición).

- **2026-10-06 — Extensión y flujo de token nunca ejecutados en un browser real.**
  `apps/extension` (popup, handoff, health) y el camino de autenticación de Fase 10
  (`<meta name="lmd-token">` → header en `apps/web/src/lib/api.ts`, cookie
  `HttpOnly`/`SameSite=Strict`, SSE autenticado por cookie porque `EventSource`
  no manda headers) están cubiertos por tests de lógica pura y de contratos, pero
  **nunca se ejecutaron en Chrome ni Firefox**.
  *Hipótesis:* lo único que puede fallar sin que los tests lo detecten es (1) el
  render del popup y su CSS, (2) la CSP default de MV3 bloqueando el `fetch` del
  popup a `127.0.0.1`, (3) el `SameSite=Strict` de la cookie contra el SSE, y
  (4) la detección Chrome/Firefox del bridge (`apps/extension/src/browser/index.ts`).
  *Estado:* abierto por decisión explícita del usuario — no se prueba hasta Fase 16
  (Packaging), que es la primera fase donde la extensión se distribuye de verdad.
  *Acción:* en Fase 16, con `apps/extension/dist` compilado: cargar la extensión
  unpacked en Chrome y Firefox contra el servicio real y recorrer el checklist de
  arriba. Si algo falla, se corrige ahí (Fase 16/17) y se promueve a Regla de Oro.

  (La observación anterior del `.gitignore` heredado se cerró en Fase 8 y vive en
  `observations_archive.md`, blindada por la Regla de Oro 8.1.)