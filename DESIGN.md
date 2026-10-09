---
name: Local Media Downloader
description: A local-first media transfer tool with a durable job queue — dark, dense, and honest about state.
colors:
  ground: "#0b0d10"
  panel: "#12151a"
  raised: "#1a1e25"
  well: "#0e1116"
  seam: "#21262e"
  seam-strong: "#2e343f"
  ink: "#e8edf4"
  ink-2: "#99a3b3"
  ink-3: "#6a7382"
  ink-4: "#454c57"
  accent: "#38bdf8"
  accent-strong: "#0ea5e9"
  accent-dim: "#075985"
  accent-ink: "#bae6fd"
  accent-wash: "#0b2b3d"
  ok: "#34d399"
  warn: "#fbbf24"
  crit: "#f87171"
  idle: "#6a7382"
typography:
  headline:
    fontFamily: "'Archivo', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
  title:
    fontFamily: "'Archivo', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "'Archivo', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "'Archivo', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
  data:
    fontFamily: "'Archivo', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "'tnum' 1"
rounded:
  md: "8px"
  lg: "12px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.well}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.crit}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.lg}"
    padding: "16px"
  tab-active:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "6px 10px"
---

# Design System: Local Media Downloader

## Overview

**Creative North Star: "The Transfer Bay"**

The dashboard is the panel face of the machine doing the work: a media transfer rack. Graphite ground a half-step off pure black, panels separated by hairline seams instead of shadows, one step of elevation between ground, panel and raised control. It borrows the transfer bay's calm, dense competence — the sense of an appliance that reports rather than performs. Nothing here tries to be exciting; it tries to be legible at a glance and honest about state, because the person looking at it wants to know one thing: *is my download moving?*

The incumbent layout the user likes is preserved: a slim rack header with the mark and wordmark on the left and seven screen tabs on the right, one centred content column below. Density is a feature: rows are tight, type is small, and the whole queue's state can be read in one horizontal scan of stage rails. Motion exists only where it carries meaning — a lit segment pulses while its stage emits progress and stops the moment it does not. Under `prefers-reduced-motion` the parallax, pulses and spinner turns switch off rather than slow down.

The category default — a flat grey card list with one blue accent doing nothing in particular — is the anti-reference. Sky is reserved for exactly one meaning, colour never carries state alone, and every number that counts is tabular so digits do not dance.

**Key Characteristics:**

- Dark graphite ground with hairline-seam panels; zero drop shadows anywhere.
- One accent (sky) that means only "happening right now" — running stages, selection, focus.
- Tabular figures for every moving number (bytes, speed, ETA, percent, timestamps).
- The stage rail — download → process → validate → commit — as the signature state readout on every job.
- Destructive actions outlined, isolated by empty space, never filled.
- Self-hosted everything: the dashboard needs no internet to look correct.

## Colors

A cool graphite scale carrying ink, with one sky accent for liveness and three lamp colours for state — the palette of an unlit equipment room, not a neon terminal.

### Primary

- **Sky / Live Accent** (`#38bdf8`, token `accent`): the only saturated colour on any surface. It means something is happening right now: the active stage segment, the progress fill, focused inputs, selected filter pills, in-flight row tint. `accent-strong` (`#0ea5e9`) is its hover state on primary buttons.

### Secondary

- **Accent Ink** (`#bae6fd`, token `accent-ink`): readable sky for text on accent washes (selected pills, tab text on selection).
- **Accent Wash** (`#0b2b3d`, token `accent-wash`): the deep sky tint used as selection background and in-flight row tint — sky meaning carried by the ground, not the text.
- **Accent Dim** (`#075985`, token `accent-dim`): borders and `::selection` background where sky must whisper.

### Tertiary (state lamps — never used without a lamp dot or a word)

- **Lamp Green** (`#34d399`, token `ok`): completed jobs, detected tools, saved confirmations.
- **Lamp Amber** (`#fbbf24`, token `warn`): needs-recovery, retry waits, warnings — and a stage gone stale past its budget.
- **Lamp Red** (`#f87171`, token `crit`): failed jobs, errors, the `no` of a missing tool, destructive action text.
- **Lamp Grey** (`#6a7382`, token `idle`): cancelled and queued jobs; identical value to `ink-3`, kept as its own token because it names a state, not a tone.

### Neutral

- **Ground** (`#0b0d10`, token `ground`): the page itself, a half-step off pure black with a cool cast.
- **Panel** (`#12151a`, token `panel`): cards, tables, inputs — the one-step-elevated working surface.
- **Raised** (`#1a1e25`, token `raised`): controls in their resting height: secondary buttons, active tab, hover surfaces.
- **Well** (`#0e1116`, token `well`): inset surfaces — progress tracks, the sticky header, and the text colour on primary buttons (the brightest thing on a filled sky button is its ink).
- **Seam** (`#21262e`) / **Seam Strong** (`#2e343f`): the 1px hairlines that separate every panel; `seam-strong` is a panel's hover border and the scrollbar thumb.
- **Ink scale** (`ink` `#e8edf4` / `ink-2` `#99a3b3` / `ink-3` `#6a7382` / `ink-4` `#454c57`): primary text, secondary text, tertiary text, disabled/placeholder.

### Named Rules

**The One Accent Rule.** Sky appears only where something is live: a running stage, a selection, a focus, an in-flight row. Nothing decorative, no chart, no illustration may borrow it. If sky shows up on a resting surface, the surface is lying about being active.

**The No Colour Alone Rule.** State colour is always paired with a shape or a word: a lamp dot plus the state name in `StateBadge`, a rail summary line under every stage rail, `yes`/`no` words beside the Diagnostics lamps. A hue shift is never the only carrier of meaning.

## Typography

**Display Font:** Archivo, self-hosted (WOFF2 subsets in `public/fonts/`, `font-display: swap`, system-ui fallback stack — the dashboard renders identically offline)
**Body Font:** Archivo (same stack)
**Label/Mono Font:** system mono stack (`ui-monospace, Cascadia Mono, Segoe UI Mono, Menlo`) — used only for raw URL lists in Batch, never for UI chrome

**Character:** A single workhorse grotesque at four small sizes. Archivo was drawn for high-density text and carries `tnum` tabular figures, which is the whole reason it is here: bytes, speed and ETA count upward several times a second and must not jitter.

### Hierarchy

- **Headline** (600, 18px, 1.4): one per screen — "Dashboard", "History", "Settings". Never larger.
- **Title** (500, 14px): job titles, card headings, table body that leads.
- **Body** (400, 14px, 1.5): paragraphs and control labels; one-liners only, nothing here is long-form.
- **Label** (500, 12px): state words, table headers, definition-list keys.
- **Data** (400, 12px, `tnum`): every number that changes over time — percentages, byte pairs, speeds, ETAs, timestamps, priorities, attempt counts. Rendered with the `.fig` utility (`font-variant-numeric: tabular-nums`).

### Named Rules

**The Tabular Figure Rule.** Any number that updates over time renders with `.fig`. A proportional "1" next to a tabular "0" makes a whole row shudder; digits in motion must be tabular.

**The One Face Rule.** Archivo for everything except raw user-entered URLs. Introducing a display face for headlines is a category-costume mistake: this is a working panel, not a poster.

## Layout

One centred column (`max-w-5xl`, 1024px, 24px side padding) under a sticky header (`bg-well`, solid — no backdrop blur). No router: seven screens switch in place behind the same header, with `?url=` as the only deep link. The content stack uses a 24px section gap; cards inside it stack at 12px; rows inside cards sit at 6–8px. Tables are full-width with 12px cell padding and their own horizontal scroll on narrow viewports; `scrollbar-gutter: stable` on `html` keeps the column from jumping when a table overflows. The single breakpoint that changes structure is `sm` (640px): control rows collapse from `flex-row` to `flex-col`, and the header tabs wrap. Two fixed layers sit behind the content at `z-index: -2/-1`: a static radial glow (`.lmd-ground`) and the seam-grid texture (`.lmd-texture`) — the only scroll-reactive element on the page, moved by `translate3d` in a rAF-coalesced listener.

## Elevation & Depth

No shadows. Anywhere. Depth is conveyed by tonal steps and hairline seams: ground → panel → raised is exactly one step each, and panels are separated by 1px `seam` borders rather than cast shadows. The ground's radial glow is atmosphere (it dims the seam grid toward the fold), not elevation. Focus is the one thing that draws a line around itself: a 2px `outline` in `accent` with a 2px offset, applied globally to `:focus-visible`.

### Shadow Vocabulary

None. The absence is the system: if a design instinct reaches for `box-shadow`, it should reach for `border: 1px solid seam` or one step up the panel scale instead.

### Named Rules

**The Seam Rule.** A panel is bounded by a 1px hairline (`seam`), and its hover is a brighter hairline (`seam-strong`) — never a shadow, never a glow. Elevation is one step deep, and that step is a colour change.

## Shapes

Controls round at 8px (`rounded-md`), cards and table containers at 12px (`rounded-lg`), and anything that reads as a lamp, pill or progress segment is fully round (`pill`). The only imagery is the mark: the project bolt on a dark tile with an 11px radius and a 1px keyline — the same drawing as the favicon. Border weights are uniform: 1px everywhere, no exceptions.

## Components

### Buttons

- **Shape:** 8px radius.
- **Primary:** filled `accent` with `well` text (a filled sky button inverts: dark ink on bright sky) — the one filled control on any screen. Padding 6px/12px.
- **Secondary:** `raised` fill, `seam` hairline, `ink` text — the default control.
- **Ghost:** transparent, `ink-2` text, fills `raised` on hover — table-row actions like Retry.
- **Danger:** transparent, `crit` text and border, hover fills `crit` at 10% — Cancel, Run cleanup. Never filled at rest.
- **Busy:** every variant replaces its icon with a `Spinner`, sets `aria-busy` and disables re-entry; the label text never changes, so screen-reader queries and tests stay stable.
- **Hover / Focus:** colour transitions at 150ms; keyboard focus is the global 2px accent outline.

### Chips

- **Style:** fully round filter pills with 1px `seam` borders, `ink-3` text.
- **State:** selected fills with `accent-wash` and `accent-ink` text (`aria-pressed` reflects state); the single accent usage that means selection rather than liveness — both are "this one, now".

### Cards / Containers

- **Corner Style:** 12px radius.
- **Background:** `panel` over the ground.
- **Shadow Strategy:** none — see The Seam Rule. Hover brightens the border to `seam-strong`.
- **Border:** 1px `seam`.
- **Internal Padding:** 16px.

### Inputs / Fields

- **Style:** `panel` fill, 1px `seam` border, 8px radius; number inputs carry `.fig` so typed priorities align.
- **Focus:** border shifts to `accent-dim` plus the global focus outline.
- **Disabled:** `not-allowed` cursor and 55% opacity.

### Navigation

- **Style:** the sticky header's tab row. Inactive tabs are `ink-3` text that lifts to `panel` fill and `ink-2` on hover; the active tab is `raised` with `ink` text and `aria-current="page"`. Each tab leads with a 14px stroke icon drawn from the in-repo icon set (`currentColor`, uniform 1.5px stroke).

### Stage Rail (signature component)

The pipeline `download → process → validate → commit` as four fixed 4px-tall segments across the full card width. It renders only while a stage is in play, or while a job stopped inside one — finished and pre-pipeline jobs show the summary line alone, so a completed card carries one bright bar, never a second dim one. The stage currently running fills in `accent` and pulses; finished stages hold a dimmed sky; a failed stage holds `crit`, a cancelled or recovery-halted one `warn`. Its budgeted honesty is the point: when a stage goes quiet past its staleness budget (15s download, 90s process, 45s validate, 20s commit — FFmpeg gets the long budget on purpose), the active segment turns amber, stops pulsing, and the summary line says "no progress". A rail never claims progress that is not arriving. An `aria-label` ("Pipeline: Download") carries the state to screen readers.

### State Badge

A 6px lamp dot plus the state word in its tone colour (compact variant drops the visible word and keeps it in `sr-only`). The lamp, not the hue, is the primary carrier — the word makes it unambiguous.

## Do's and Don'ts

### Do:

- **Do** serve every asset self-hosted — fonts, favicon, icons. A CDN link in the dashboard breaks the product's core promise (local-first) and its offline behaviour.
- **Do** give every moving number `.fig` (tabular figures).
- **Do** pair every state colour with a lamp or a word.
- **Do** isolate destructive actions: outlined, alone at the end of a row, empty space around them.
- **Do** disable motion entirely under `prefers-reduced-motion` — the parallax stops, pulses stop, spinner turns slow to a near-static ring.
- **Do** keep interactive elements showing `cursor: pointer` — it is set globally on `button`, `[role=button]`, `a`, `select`, `label[for]`; a control that looks inert is a control users think is broken.

### Don't:

- **Don't** use sky for anything resting, decorative or illustrative. It means "happening right now" or "this one, selected" — nothing else.
- **Don't** show a spinner where no request is in flight. A spinner is a claim about work; a stale table gets a stale signal (the amber rail), not a busy animation.
- **Don't** cast shadows or use `backdrop-filter` on scroll-tracked surfaces — blur on a sticky header re-blurs every scroll frame.
- **Don't** animate layout properties. Colour and opacity transitions at 150–300ms; transforms for the parallax layer only.
- **Don't** restyle state words by hand — `toneFor()` in `jobState.ts` is the single map; adding a state means adding it there once.
