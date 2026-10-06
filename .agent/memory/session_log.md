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

`Sesión 11 — 2026-10-06 — opencode/fledge-alpha-free vía OpenCode (PowerShell/Windows)`

- Sesión de cierre/verificación (sin código de producto): `gh` CLI instalado vía scoop (2.102.0) + `gh auth login` hecho por el usuario → habilitó `gh run view --log-failed`, que antes daba 403 con la API pública.
- **CI: el job `frontend` estaba en rojo desde el commit de Fase 3** (los dos OS) y nadie lo había notado; `backend` pasaba. Causa raíz: pnpm **11 eliminó** `onlyBuiltDependencies` y lo ignora en silencio, así que el install limpio en CI abortaba con `ERR_PNPM_IGNORED_BUILDS` (deno) y su postinstall nunca corría — el runtime JS de yt-dlp-ejs tampoco estaba instalado en máquinas limpias. Localmente todo pasaba porque `node_modules` ya tenía el binario de instalaciones viejas.
- Fix: `pnpm-workspace.yaml` → `allowBuilds: { deno: true }`, verificado **antes** de pushear con un clon limpio (`git clone --depth 1`, borrar `node_modules`, correr los 5 pasos exactos del job frontend: install, lint, format:check, check, test, build). Commit `cbf8277`; CI quedó **4/4 verde** (run `37512262845`).
- Commit `8666100` con las fases 7–10 pusheado (un solo commit porque `app.py` mezcla las cuatro fases).
- **Fase 11 evaluada: NO se implementa Native Messaging.** El gate de `IMPLEMENTATION_PLAN.md` exige "instalación/distribución entendidas", y eso recién existe en Fase 16 (PyInstaller + Inno Setup). Además Native Messaging solo tiene sentido para builds instalados: el MVP localhost se comunica por HTTP loopback sin él. Se reevalúa en Fase 16.
- **Decisión explícita del usuario: no probar la extensión en un browser real hasta Fase 16.** Los riesgos que eso deja abiertos quedaron escritos como observación en curso (popup/CSP MV3, cookie `SameSite=Strict` contra el SSE, detección Chrome/Firefox del bridge) con el checklist para Fase 16.
- `roadmap.md` actualizado (Fase 11 como evaluada; corregida la referencia obsoleta a `onlyBuiltDependencies`; la nota de "docs/ sin trackear" ya no aplica porque `.agent/` está versionado).

---

## HISTORIAL RELEVANTE (comprimido, detalle completo en session_log_archive.md)

- `Sesión 10 — 2026-10-06` — Fase 10: token, Host/Origin, bind loopback, SSRF guard, sanitización de filenames, rate limit; Reglas 10.1, 10.2, 10.3.
- `Sesión 9 — 2026-10-06` — Fase 9: extensión MV3, handoff `?url=`, health Connected/Offline; Regla 9.1.
- `Sesión 5 — 2026-10-06` — Fases 4 (FFmpeg/FFprobe adapters) + 5 (execution planner). 163 tests.
- `Sesión 4 — 2026-10-04` — Fase 3 yt-dlp adapter; quality_score reescrito;
  Deno 2.9.6 vía pnpm; auditoría SQL (cursor keyset + idx_jobs_sort). 141 tests.
- `Sesión 3 — 2026-10-04` — Fase 2: SQLite + job state machine.
- `Sesión 2 — 2026-10-04` — Fase 1: skeleton FastAPI+Granian.
- `Sesión 1 — 2026-10-04` — Fase 0: monorepo uv+pnpm.
