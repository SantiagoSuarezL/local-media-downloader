# Observaciones — ARCHIVO — local-media-downloader

> Observaciones cerradas verbatim. No se lee automático.

## Archivo de observaciones

### 2026-10-08 → cerrada 2026-10-10 — Smoke del bundle frozen (→ Regla de Oro 17.10)

- **2026-10-08 — Smoke del bundle frozen pendiente (reserva del cierre Fase 16).**
  Target `apps/api/lmd.spec` + `lmd_entry.py` + `packaging/stage_bundle.ps1`.
  El spec portable compila (PyInstaller 6.22.3 onedir OK, 3 builds); el primer
  boot frozen falló por imports relativos (`__main__.py` top-level → shim
  `lmd_entry.py` creado); los 2 intentos de smoke se cayeron por falta de
  recursos de la laptop (uno dejó 5 `ffmpeg` zombie de los tool probes →
  matados; `dist/`+`build/` ~600 MB eliminados, todo gitignored).
  Nota Sesión 33: el bundle incluye `yt_dlp_ejs` (`collect_all` + hiddenimport
  en `lmd.spec`) y `deno.exe` se stageaba.
- **Cierre 2026-10-10 (Sesión 36):** el smoke corrió por fin — primero como paso
  del nuevo workflow Release en CI y FALLEÑO (`frozen bundle never served its
  banner`, run 38026191613), destapando la causa raíz que la laptop nunca dejó
  ver: Granian spawnea el worker con `multiprocessing` aunque `workers=1`
  (`MPServer`, `BUILD_GIL True` en 3.12) y un exe frozen re-ejecuta
  `sys.executable` como hijo — sin `multiprocessing.freeze_support()` en
  `lmd_entry.py`, el "worker" arrancaba otro servidor y el banner jamás se
  servía. Fix en `lmd_entry.py` + smoke con fail-fast y captura/dump de
  stdout/stderr (Regla de Oro 17.10). Verificado LOCAL de punta a punta
  (build → boot → banner → shell con token → kill limpio) y en CI: run
  38067647416 **success** con "Smoke the frozen bundle" en verde. Blindado en
  código (freeze_support) + workflow (el smoke corre en cada release).

### 2026-10-04 → cerrada 2026-10-06 — `.gitignore` heredado de plantilla Python (→ Regla de Oro 8.1)

- **2026-10-04 — `.gitignore` heredado de plantilla Python.** El `.gitignore` raíz
  (commit inicial) traía ~220 líneas de plantilla que no aplican al proyecto, con
  patrones que pueden volcar código real sin avisar: `lib/`, `var/`, `build/`,
  `target/`, `downloads/`, `share/python-wheels/`. Si más adelante se crea un `lib/`
  con TypeScript compartido o un `build/` de artefactos, desaparecerían del repo en
  silencio.
  *Hipótesis:* reducir el `.gitignore` a las líneas realmente necesarias.
  *Estado:* abierto — no bloquea la Fase 0.
  *Acción:* decidir en la Fase 1, cuando exista un `.venv` y un build real para
  contrastar cada patrón con `git check-ignore`. (Relacionado: Regla de Oro 1.2)
- **Cierre 2026-10-06 (Fase 8):** la hipótesis se confirmó en producción — el patrón
  `lib/` ignoraba `apps/web/src/lib/` (código fuente real) en silencio. Se anclaron
  a raíz todos los patrones de directorio de plantilla (`/lib/`, `/build/`, `/var/`,
  `/target/`, `/dist/`, `/tmp/`, `/temp/`, `/cover/`, `/coverage/`, etc.);
  `apps/web/dist/` y `apps/extension/dist/` siguen ignorados por líneas explícitas.
  Blindado en código + Regla de Oro 8.1.
