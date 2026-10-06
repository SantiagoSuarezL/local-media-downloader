# Observaciones — ARCHIVO — local-media-downloader

> Observaciones cerradas verbatim. No se lee automático.

## Archivo de observaciones

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
