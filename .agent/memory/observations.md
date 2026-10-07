# Observaciones — local-media-downloader

> 5to archivo del protocolo, explícito (no un archivo suelto). Solo
> observaciones EN CURSO (no resueltas todavía, requieren más monitoreo).
> Una vez que una observación se convierte en regla de código confirmada,
> se archiva en `observations_archive.md` y queda solo una línea de cierre
> acá apuntando a la Regla de Oro correspondiente en `lessons_learned.md`.

Formato de cada entrada: fecha, target/módulo, observación, hipótesis, estado, acción.

## En curso

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