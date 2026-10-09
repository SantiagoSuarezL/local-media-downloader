# Local Media Downloader

Download and transform media locally from almost any supported URL — YouTube,
TikTok, X/Twitter and every site supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

A local-first modular monolith with a durable job scheduler: the service runs
entirely on your machine (loopback only, no telemetry, no accounts), the
dashboard is served by the same process, and a browser extension hands off
the page you are watching with one click.

## Highlights

- **Download** — best available quality by default, or pick container, codec,
  bitrate, framerate; presets for GIF, WebP, WhatsApp sticker and mobile.
- **Transform** — trim, resize, crop, audio normalization (loudnorm), audio
  extraction to MP3, stream copy when no re-encode is needed.
- **Reliable queue** — jobs persist in SQLite and survive crashes; live
  progress over SSE, cancel/retry, bounded retries with backoff.
- **Batch & history** — multi-URL submit, paginated history with manual retry,
  automatic retention (URLs redacted after 7 days, history kept 30 days).
- **Local security model** — binds to loopback only, per-installation token,
  strict Host/Origin checks, no secrets in logs.
- **Extension** — one click on any page sends its URL to the dashboard.

## Requirements

- Windows, macOS or Linux
- [uv](https://docs.astral.sh/uv/) (brings Python 3.12+ and every backend
  dependency: yt-dlp, curl-cffi — TLS impersonation some sites require — etc.)
- Node.js >= 22 with pnpm (builds the dashboard and the extension; also brings
  Deno, the JS runtime yt-dlp needs internally)
- FFmpeg + FFprobe on your `PATH` (or point `LMD_FFMPEG`/`LMD_FFPROBE` at them)

## First-time setup

```bash
uv sync          # Python environment + backend (editable)
pnpm install     # JS workspace: web, extension, shared contracts
pnpm build       # builds dashboard + extension into their dist/ folders
```

That is all: on first start the service creates its own `data/` directory
(SQLite database, job folders, logs) and a per-installation token. There is no
login screen — the token is handed to the dashboard automatically.

## Run

```bash
uv run --package local-media-downloader-api python -m local_media_downloader
```

Then open **http://127.0.0.1:8765/**. You should see the dashboard with a
green service status. `Ctrl+C` stops the service in about a second.

### Downloading a video

1. **Resolve** — paste a URL (or use the extension, below) and resolve it to
   see title, duration and available formats.
2. **Create the job** — pick an intent (e.g. *best available video*, an audio
   MP3, or a preset) and submit. Adjust trim/resize/crop/codec options if you
   need them.
3. **Watch it run** — the Jobs view shows live progress, stage
   (download → process → validate → commit) and a cancel button while active.
4. **Collect the file** — finished media lands in
   `~/Downloads/Local Media Downloader/` by default. Organize it with
   `flat` / `by_extractor` / `by_date` output rules (Settings or
   `LMD_OUTPUT_RULE`).

### The browser extension

1. Build it once (`pnpm build` already did) and load
   `apps/extension/dist` as an unpacked extension:
   - Chrome/Edge/Brave: `chrome://extensions` → developer mode →
     *Load unpacked*.
   - Firefox: `about:debugging` → *Load temporary add-on* → any file in
     `apps/extension/dist`.
2. Pin it. The popup shows **Connected** when the service is running.
3. On any video page, click the extension → *Open in Local Media Downloader*:
   the dashboard opens with Resolve pre-filled with that URL.

The extension only ever talks to `127.0.0.1`/`localhost` — its permission set
is `activeTab` + `storage`, nothing else.

## Where things live

| Path | Contents |
|---|---|
| `~/Downloads/Local Media Downloader/` | Final media files (override: `LMD_OUTPUT_ROOT`) |
| `./data/` (or `LMD_DATA_DIR`) | `app.db`, job temp folders, cache, logs |
| `./apps/web/dist` | Dashboard build served by the API |

Retention defaults (tunable in Settings or via env): source URLs are redacted
after **7 days** (a SHA-256 hash remains for dedupe), job history is kept
**30 days**, temporary job folders are cleaned after **24 hours**.

## Configuration

Every value is an environment variable prefixed with `LMD_`; the important ones:

| Variable | Default | Meaning |
|---|---|---|
| `LMD_PORT` | `8765` | Service port |
| `LMD_HOST` | `127.0.0.1` | Bind address (loopback only — non-loopback refuses to start) |
| `LMD_DATA_DIR` | `./data` | Database, job folders, logs |
| `LMD_OUTPUT_ROOT` | `~/Downloads/Local Media Downloader` | Where finished media goes |
| `LMD_OUTPUT_RULE` | `flat` | `flat` / `by_extractor` / `by_date` |
| `LMD_LOG_LEVEL` | `INFO` | Log level (WARNING quiets the console) |
| `LMD_SOURCE_URL_RETENTION` | `7days` | How long full URLs are kept |
| `LMD_HISTORY_RETENTION_DAYS` | `30` | History lifetime |
| `LMD_TEMPORARY_RETENTION_HOURS` | `24` | Temp folder cleanup |
| `LMD_SCHED_MAX_ACTIVE` / `_DOWNLOADS` / `_ENCODERS` | `3` / `2` / `1` | Concurrency budget |
| `LMD_FFMPEG` / `LMD_FFPROBE` | auto | Explicit paths to the binaries |

## Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Extension says **Offline** | Service not running, or a different port — set the address in the popup's service settings. The first health check after startup can take a few seconds while tools are detected. |
| `UNSUPPORTED_SOURCE` | The site or URL is not supported by the extractor. |
| `TOOL_OUTDATED` | The site changed and yt-dlp needs an update: `uv sync --upgrade-package yt-dlp` then restart. |
| `SOURCE_UNAVAILABLE` | The video is gone, private, or the site refused this IP for that post — retry later or from another network. |
| `AUTH_REQUIRED` / `AGE_RESTRICTED` | Sign-in-only or age-gated media; not downloadable by design. |
| `GEO_RESTRICTED` | Not available from your location. |
| `DRM_PROTECTED` | DRM media can never be processed. |
| `NETWORK_ERROR` / `TIMEOUT` | Transient network problem — retry, the job keeps its place. |
| `INSUFFICIENT_DISK` | Less than 512 MB free for the working directory. |
| Port already in use | `LMD_PORT=8766` (the extension popup has a matching service-address field). |

## Development setup

Requires [uv](https://docs.astral.sh/uv/), Node.js >= 22 and pnpm.

```bash
uv sync                    # Python env + editable apps/api
pnpm install               # JS workspace (web, extension, contracts)
uv run pre-commit install # git hooks: ruff + prettier on every commit
```

### Working on the dashboard

Production serves the built dashboard from the API itself. For a hot-reload
dev loop instead:

```bash
pnpm dev   # Vite on http://127.0.0.1:5173, proxying /api to the service
```

Keep the service running on its own terminal; both share the same token
cookie, so logging in once at `:8765` covers `:5173` too.

## Checks

Run the same gates as CI before pushing:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright && uv run pytest
pnpm lint && pnpm format:check && pnpm check && pnpm test && pnpm build
```

`docs/TESTING.md` is the gate playbook: exact order, what each suite covers,
and the mandatory stop-and-handoff policy when a gate is red.

## Layout

```text
apps/api            FastAPI + Granian service, job scheduler, execution adapters
apps/web            Svelte 5 + Vite + Tailwind dashboard (static assets)
apps/extension      Manifest V3 extension with a thin browser adapter
packages/contracts  Shared API contract types
docs/               Product and architecture specs
data/               Runtime data (git-ignored): app.db, jobs, cache, logs
```

`data/`, `dist/`, `.venv/`, `node_modules/`, `.claude/`, `.opencode/` and
`graphify-out/` are git-ignored. `uv.lock` and `pnpm-lock.yaml` are versioned.

## Documentation

- `docs/PRD.md` — product requirements
- `docs/ARCHITECTURE.md` — system design
- `docs/TECHNICAL_SPEC.md` — technical specification
- `docs/IMPLEMENTATION_PLAN.md` — phased implementation plan
- `docs/TESTING.md` — quality gates playbook
- `THIRD_PARTY_NOTICES.md` — bundled third-party components
