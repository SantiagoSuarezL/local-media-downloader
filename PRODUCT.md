# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers and technically capable users who want a local, open-source media
tool (`docs/PRD.md` §5). Single user per installation: the service runs as a
local desktop service, not a shared or multi-tenant system.

Two confirmed scenes:

- Someone browsing a video page who wants that video on their disk, without
  installing a cloud account or accepting a proprietary backend. They arrive
  from the browser extension popup, not from typing a URL.
- Someone managing a queue of downloads already in flight, wanting to know what
  is happening right now and to intervene (cancel, retry, reprioritize).

## Product Purpose

Accept a media page URL, resolve the media capabilities available for it, let
the user pick an output intent, download the source locally, optionally
transform it, and place the final artifact in a user-selected local directory
(`docs/PRD.md` line 17).

The MVP is successful when a user can install the application, open a supported
public video page, click the extension, choose a format, download it locally,
and recover gracefully after interruption (`docs/PRD.md` line 390).

Success is a file on disk at the right path with the right properties, and a
job list the user can trust.

## Positioning

Media bytes never leave the machine. No proprietary cloud backend, no VPS, no
remote database, no subscription for core functionality (`docs/PRD.md` line 19).

The mechanism a neighboring product could not truthfully copy: a durable job
scheduler whose state lives in local SQLite and survives crashes, power loss and
interruption, driven by a bounded concurrency budget, with every artifact landing
in a real local output directory. There is no login screen — the per-installation
token is handed to the dashboard automatically.

## Operating Context

- The service is a local process on loopback. A non-loopback bind address
  refuses to start.
- The dashboard is served by the same process that does the work: FastAPI mounts
  the Svelte build at `/`. No Node server in runtime.
- The browser extension hands off the current page URL by opening
  `<service>/?url=<encoded>`; the SPA reads that parameter at startup to
  prefill Resolve. It is the dominant entry path, not a convenience.
- The user configures the product with `LMD_`-prefixed environment variables and
  the Settings screen. Output root and output rule are operator-level, never
  setable per job through the API.
- Finished media lands in `~/Downloads/Local Media Downloader/` by default.
- A download is a multi-stage pipeline: download → process → validate → commit.
  Failure at any stage is a normal, expected outcome, not an edge case.
- Retention is a first-class operational behavior: source URLs are redacted
  after 7 days (a SHA-256 hash remains for dedupe), job history is kept 30 days,
  temporary job folders are cleaned after 24 hours.

## Capabilities and Constraints

Capabilities, all shipped and verified (`apps/api`, 561 fast tests + 1 smoke):

- Resolve a supported URL to title, duration and normalized formats.
- Download with best-available quality by default, or a chosen container, codec,
  bitrate, framerate; presets for GIF, WebP, WhatsApp sticker and mobile.
- Transform: trim, resize, crop, audio normalization (loudnorm), audio extraction
  to MP3, stream copy when no re-encode is needed.
- Durable queue with bounded retries and backoff, manual retry, cancel,
  reprioritization.
- Batch multi-URL submit, paginated history with cursor pagination.
- Live progress over SSE, authenticated by cookie because `EventSource` cannot
  send headers.
- Retention and cleanup, run on a schedule or manually from History.
- Desktop notifications through the dashboard.

Constraints that future work must preserve:

- **Local-first, always.** No telemetry, no accounts, no external service in the
  runtime path. A design decision that introduces a network dependency for
  appearance (hosted fonts, remote image CDNs, analytics) contradicts the
  product's core principle.
- **Security boundary in `security.py`:** loopback-only bind; `Host` and
  `Origin` must be loopback; a per-installation token is required on every
  `/api/*` except `/api/v1` and `/api/v1/health`; the token is never logged.
- **Layers:** `domain/` imports neither yt-dlp nor FastAPI; `adapters/` is the
  only place that knows external tools; `services/` orchestrates; `app.py` only
  validates and delegates.
- **SQLite is the source of truth for job state.** SSE progress is a live
  overlay, never the record. `jobs.state` is the single authority.
- **Subprocess isolation.** Workers execute yt-dlp and FFmpeg as child
  processes; no in-process tool calls.
- **Concurrency budget** defaults to 3 active / 2 downloads / 1 encoder.
- **Tokens do not depend on the global `PATH`.** `adapters/tool_paths.py` resolves
  binaries in a fixed order; diagnostics must use the same resolver the runtime
  uses.
- No routing library: the dashboard is a seven-screen switch driven by component
  state, with `?url=` as the only deep link.

Undecided: nothing blocking. Download throughput still has no hermetic
baseline (creating a job over HTTP requires live network); that gap is tracked
in project memory, not here.

## Brand Commitments

- **Name:** Local Media Downloader. Spelled out in the header today; the wordmark
  is not yet designed.
- **Visual register:** a quiet, dark, technical tool. The current surface is dark
  with a sky-blue accent, and the user has stated they like the existing page
  layout and content distribution and want it preserved.
- **Accent: sky.** The accent color is `sky` (`sky-500`/`sky-600`), used for
  progress, interactive affordances and selection. This is a confirmed
  commitment: when the existing favicon mark (violet) conflicted with it, the user
  chose to recolor the mark to sky so the accent wins.
- **Typeface: Archivo**, self-hosted from the project's own `public/` directory.
  The user asked for Google Fonts quality with a graceful fallback for people
  without internet; self-hosting satisfies both and keeps zero external requests.
- No emoji in the product UI. Icons are SVG drawn on `currentColor`.

## Evidence on Hand

Real, present in the repository:

- The working product itself, plus its README (`README.md`) and specs in `docs/`.
- `apps/web/public/favicon.svg` — the existing mark, a bolt in violet
  (`#863bff`→`#7e14ff`). To be recolored to the sky accent, not discarded.
- `THIRD_PARTY_NOTICES.md` — the license ledger for bundled components, populated
  from installed package metadata.
- Live-verified behavior: the user has run real downloads through the extension
  in a real Chromium browser (Thorium) against YouTube, Twitter and TikTok, with
  best-available quality working.

Must not be fabricated: no testimonials, user counts, benchmarks, ratings,
customer names, or throughput figures. The performance numbers that were
themselves once reported and then retracted (startup time, memory footprint) are
a standing reminder: this product does not publish performance claims that were
not re-measured.

## Product Principles

1. **The file on disk is the deliverable.** Every screen exists to move the user
   toward a correct artifact in their output directory. Interface work that does
   not shorten that path is decoration.
2. **Never show a state the system does not actually know.** A spinner implies
   work is happening; a stale table implies data is current. Both are lies when
   the underlying stream is dead. Truthful state beats smooth state.
3. **Local means local.** No design decision may introduce an external runtime
   dependency. Degrade to a system font, a system color, a static background.
4. **The pipeline is legible.** download → process → validate → commit is the
   product's spine; the user should be able to see which stage a job is in and
   what went wrong.
5. **Dense, quiet, fast.** A local tool that runs in one second should look like
   it runs in one second. No motion that outlives its meaning, no animation that
   costs a frame.

## Accessibility & Inclusion

No product-specific standard has been set by the user. Baseline web
accessibility applies and is enforced in part by the toolchain: ESLint runs
`svelte.configs['flat/recommended']`, whose a11y rules (`click-events-have-key-events`,
`no-static-element-interactions`) are active. Interaction is mouse-and-keyboard
focused today; motion sensitivity is not yet accounted for anywhere in the
codebase and must be, since rule 5 of the principles makes speed a promise to
the user.