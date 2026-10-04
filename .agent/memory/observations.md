# Observaciones — local-media-downloader

> 5to archivo del protocolo, explícito (no un archivo suelto). Solo
> observaciones EN CURSO (no resueltas todavía, requieren más monitoreo).
> Una vez que una observación se convierte en regla de código confirmada,
> se archiva en `observations_archive.md` y queda solo una línea de cierre
> acá apuntando a la Regla de Oro correspondiente en `lessons_learned.md`.

Formato de cada entrada: fecha, target/módulo, observación, hipótesis, estado, acción.

## En curso

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