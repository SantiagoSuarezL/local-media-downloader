/**
 * Icon registry, hand-authored rather than pulled from a package.
 *
 * Every glyph is 24x24, stroke-based, `currentColor`, stroke-linecap/linejoin
 * round, and drawn on the same optical weight so a 16px next to a 20px reads as
 * one set. Keeping it local means the dashboard ships zero icon dependencies,
 * which the local-first constraint in PRODUCT.md requires anyway.
 *
 * Paths are stored as raw markup strings so an icon can compose (several
 * `<path>` children, a circle plus a line). No per-icon props, no dynamic
 * imports: the whole set is under a kilobyte and always resident.
 */

export const ICON_PATHS = {
  /** Four panes: the queue at a glance. */
  dashboard: [
    '<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/>',
    '<rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/>',
    '<rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
    '<rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
  ],
  /** Crosshair: point at a URL and read what it offers. */
  resolve: [
    '<circle cx="12" cy="12" r="7"/>',
    '<path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>',
  ],
  /** Three rules, the last short: a queue with a ragged end. */
  batch: ['<path d="M4 7h16M4 12h16M4 17h10"/>'],
  /** A film frame: the one job in detail. */
  job: ['<rect x="3" y="5" width="18" height="14" rx="2"/>', '<path d="M7 5v14M17 5v14M3 12h18"/>'],
  /** Clock: what already ran. */
  history: ['<circle cx="12" cy="12" r="8.5"/>', '<path d="M12 7.5V12l3 2"/>'],
  /** Three slides, not a gear: sliders are the honest metaphor for tuning. */
  settings: [
    '<path d="M4 7h4M12 7h8M4 12h8M16 12h4M4 17h4M12 17h8"/>',
    '<circle cx="10" cy="7" r="2"/>',
    '<circle cx="14" cy="12" r="2"/>',
    '<circle cx="10" cy="17" r="2"/>',
  ],
  /** A pulse trace: the service reporting on itself. */
  diagnostics: ['<path d="M3 12h4l3-7 4 14 3-7h4"/>'],
  refresh: ['<path d="M20 12a8 8 0 1 1-2.34-5.66"/>', '<path d="M20 4.5v5h-5"/>'],
  cancel: ['<path d="M6 6l12 12M18 6L6 18"/>'],
  retry: ['<path d="M4 12a8 8 0 1 0 2.34-5.66"/>', '<path d="M4 4.5v5h5"/>'],
  start: ['<path d="M7.5 4.5v15l12-7.5z"/>'],
  download: [
    '<path d="M12 3.5v10.5M7.5 10l4.5 4.5L16.5 10"/>',
    '<path d="M4 16.5V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2.5"/>',
  ],
  check: ['<path d="M4.5 12.5l5 5 10-11"/>'],
  alert: ['<path d="M12 4l8.5 15H3.5L12 4z"/>', '<path d="M12 10v3.8M12 16.9v.2"/>'],
  info: ['<circle cx="12" cy="12" r="8.5"/>', '<path d="M12 11.2V16M12 8.1v.2"/>'],
  chevronRight: ['<path d="M9 5l7 7-7 7"/>'],
  folder: [
    '<path d="M3 7a2 2 0 0 1 2-2h3.6L10.4 7H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
  ],
  cleanup: ['<path d="M4 7h16M10 4h4M6.5 7l.9 13h9.2l.9-13"/>', '<path d="M10 11v6M14 11v6"/>'],
  search: ['<circle cx="11" cy="11" r="6.5"/>', '<path d="M15.8 15.8L21 21"/>'],
} as const

export type IconName = keyof typeof ICON_PATHS

export const ICON_NAMES = Object.keys(ICON_PATHS) as IconName[]
