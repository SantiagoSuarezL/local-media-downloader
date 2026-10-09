---
version: 1
slug: "apps-web"
primary_target: "apps/web"
related_targets: []
---

# Surface brief — dashboard (apps/web)

## Scope and mode

`apps/web`: the Svelte 5 dashboard served by the FastAPI service at `http://127.0.0.1:8765/`.
Seven screens switched by component state (Dashboard, Resolve, Batch, Job details,
History, Settings, Diagnostics), plus the `?url=` extension handoff.

Mode: **Operate.** The visitor came to get a download done or to watch a queue run.
Scanability, state legibility and speed outrank expression.

## Audience, job, action

Single user per installation: a developer or technically capable user managing media
locally. Two scenes dominate: (a) arriving from the extension popup with a URL already
in hand, wanting the file; (b) watching an in-flight queue and intervening
(cancel, retry, reprioritize).

Primary action: submit a URL and watch it resolve, then watch it run.
Data read first: job state, stage, percentage, bytes, speed, ETA.
Proof/content: the user's own jobs, titles, URLs, and real byte counts.

Constraints carried from PRODUCT.md: loopback only, no external runtime dependency
(no hosted fonts, no CDN, no analytics), motion must cost no frame, dark-first.

## Direction contract

THESIS: A local transfer tool should look like the panel of the machine doing the
transfer. The category default for a downloader dashboard is a flat grey card list
with one blue accent doing nothing in particular; this surface refuses that and makes
the pipeline itself the organizing idea.

OWN-WORLD: Graphite ground a half-step off pure black. Panels separated by hairline
seams the width of a real console gap, never by drop shadow — one step of elevation
only, from ground to panel to raised control. Sky is the only accent and it means
exactly one thing: something is happening right now. Every moving number
(percentage, bytes, speed, ETA) is set in tabular monospaced figures so digits do not
dance as they count. State is carried by a small status lamp, not by color alone.
Archivo for text, tabular figures for data. Destructive actions — Cancel, Run
cleanup — sit alone with deliberate empty space around them.

STORY: The visitor pastes a URL or arrives from the extension, resolves it, picks an
intent, and starts a job. From then on the app never has to ask what is happening:
the stage rail says which of the four stages is lit, the figures say how far, and a
rail that has not advanced in a while says so by not moving.

FIRST VIEWPORT: A full-width rack header carrying the mark and wordmark at left, the
seven screen tabs at right as a row of rack buttons with the active one raised by one
step and lit in sky. Below it, the Dashboard: a column of job cards, each with its
stage rail across the full card width directly under the title, so the state column of
the whole queue can be scanned in one horizontal read. Content stays centred in the
existing max-width column — the incumbent layout the user likes is preserved.

FORM: transfer bay / media transfer rack panel. Position 3 of 7 grounded candidates.
Seed key 163299e4.

Raise (from `digital-design-canon-dark-first-developer-console`, declared verdict
**declined as a world, adopted as discipline**): hairline seams instead of shadow,
one-step elevation, focus-gated destructive actions. Declined: terminal type face,
blinking cursor, bezel — an Operate surface must not become a costume of the
instrument its visitor operates.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish
review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Memorable moment

The **stage rail** on every job card: the pipeline
`download → process → validate → commit` drawn as four fixed segments with the live
one lit in sky. It is simultaneously the signature move, the state readout and the
answer to "is it stuck?" — a rail whose lit segment does not advance is visibly stuck,
without needing a spinner to lie about it.

## Unresolved decisions

- Whether the grain layer ships at all on machines where
  `prefers-reduced-transparency` is set.
- Whether the History table's stage rail collapses to a dot at the `sm` breakpoint.
