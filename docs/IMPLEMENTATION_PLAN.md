# Implementation Plan — Local Media Downloader

## 0. Rule

This document is an implementation roadmap, not permission to implement everything at once.

OpenCode should complete one phase at a time, run tests, verify behavior, and avoid introducing dependencies before the phase that requires them.

---

# Phase 0 — Repository foundation

## Objectives

Create the monorepo and development standards.

### Deliverables

```text
apps/api
apps/web
apps/extension
packages/contracts
docs
```

Configure:

- uv;
- `.venv`;
- Python version;
- `pyproject.toml`;
- `uv.lock`;
- pnpm workspace;
- TypeScript;
- Svelte 5;
- Vite;
- Tailwind;
- linting;
- formatting;
- testing.

### Acceptance

- Python environment can be created with uv.
- Backend starts locally.
- Svelte app builds with Vite.
- Extension builds.
- CI can run lint/type/test/build.
- No unnecessary runtime dependency is introduced.

---

# Phase 1 — Local service skeleton

## Objectives

Create FastAPI + Granian service.

### Features

- `/api/v1/health`;
- configuration;
- local bind;
- version reporting;
- structured logging;
- error handling.

### Acceptance

The service starts on localhost and reports:

```text
API: OK
yt-dlp: detected/not detected
yt-dlp-ejs: detected/not detected
Deno: detected/not detected
FFmpeg: detected/not detected
FFprobe: detected/not detected
database: OK
storage: OK
```

---

# Phase 2 — SQLite + job state machine

## Objectives

Introduce durable state.

### Features

- database initialization;
- WAL;
- schema migrations/versioning;
- job table;
- job events;
- state transitions;
- transaction boundaries.

### Required states

```text
CREATED
RESOLVING
READY
QUEUED
DOWNLOADING
PROCESSING
VALIDATING
COMMITTING
COMPLETED
FAILED
CANCEL_REQUESTED
CANCELLED
RETRY_WAIT
RECOVERY_REQUIRED
```

### Acceptance

A job can be created, updated, queried, and recovered after process termination.

---

# Phase 3 — yt-dlp adapter

## Objectives

Integrate yt-dlp without coupling the domain to its CLI.

### Features

- version detection;
- metadata extraction;
- format normalization;
- error mapping;
- subprocess lifecycle;
- structured progress parsing.

### Acceptance

A supported public test URL can be resolved into normalized `MediaInfo`.

The rest of the application does not depend directly on yt-dlp's raw JSON schema.

Diagnostics report the installed yt-dlp version and flag when it may be outdated.

---

# Phase 4 — FFmpeg/FFprobe adapters

## Objectives

Build media-processing abstraction.

### Features

- version detection;
- FFprobe metadata;
- stream inspection;
- remux;
- transcode;
- audio extraction;
- video-only output;
- validation.

### Acceptance

Given a local source fixture:

- MP4 can be produced;
- MP3 can be produced;
- audio can be removed;
- output metadata can be validated.

---

# Phase 5 — Execution planner

## Objectives

Translate user intent into safe execution plans.

### Examples

```text
best + mp4
audio + mp3
video only
remove audio
source-compatible webm
resize 720p
```

### Acceptance

Planner tests verify that:

- stream copy is preferred when possible;
- transcoding occurs only when necessary;
- unsupported combinations are rejected before execution;
- arbitrary command arguments cannot enter through user intent.

---

# Phase 6 — Scheduler + worker pool

## Objectives

Turn jobs into controlled background execution.

### Features

- queue;
- worker lifecycle;
- max concurrent downloads;
- max concurrent encoders;
- cancellation;
- retries;
- backpressure;
- resource checks.

### Initial policy

```text
total active: 3
downloads: 2
encoders: 1
```

Make these configurable.

### Acceptance

Ten submitted jobs do not create ten simultaneous FFmpeg processes.

A normalized progress model is defined and observable by the scheduler.

Progress and scheduler events are exposed over SSE (`GET /api/v1/events`).

---

# Phase 7 — Recovery and resilience

## Objectives

Make interruption safe.

Test scenarios:

### A — Application crash

Kill the service during download.

Expected:

```text
job not marked completed
job detected on restart
job recovered/requeued
```

### B — Power-loss simulation

Terminate the process abruptly and restart.

Expected:

- SQLite remains consistent;
- partial files are not presented as completed;
- job can resume/retry when possible.

### C — Disk full

Expected:

```text
INSUFFICIENT_DISK
```

No endless retry loop.

### D — Network loss

Expected:

- bounded retries;
- backoff;
- clear error state.

### E — FFmpeg crash

Expected:

- output is not committed;
- stderr is available in diagnostics;
- job becomes retryable/non-retryable based on classification.

---

# Phase 8 — Svelte web UI

## Objectives

Build the user-facing dashboard.

### Screens

```text
Dashboard
Resolve
Job details
History
Settings
Diagnostics
```

### Dashboard

```text
┌────────────────────────────────────────┐
│ Local Media Downloader                 │
│                                        │
│ Paste URL                              │
│ [_______________________________]      │
│                         [ Resolve ]     │
│                                        │
│ Recent jobs                            │
│ ────────────────────────────────────── │
│ Video A       ████████░░  80%          │
│ Video B       Completed   [Open folder]│
└────────────────────────────────────────┘
```

### Resolve view

Show:

- thumbnail;
- title;
- duration;
- source;
- quality;
- available formats;
- warnings.

### Output controls

Start with presets:

```text
Best available
MP4
MP3
Video only
No audio
WebM
```

Then expose advanced settings.

---

# Phase 9 — Browser extension

## Objectives

Provide browser-to-local-app handoff.

### MVP

Popup:

```text
Current page detected

https://example.com/...

[Open in Local Media Downloader]
```

Also:

```text
[Paste URL]
```

And a service health indicator:

```text
Local Media Downloader
● Connected   /   ○ Offline
```

### Extension responsibilities

- read current tab URL;
- authenticate to local service;
- open dashboard with URL;
- show service unavailable state.

### Acceptance

A click from a supported page opens the local app with the correct URL.

---

# Phase 10 — Security hardening

## Objectives

Treat localhost as a real security boundary.

### Implement

- loopback-only bind;
- local auth token;
- Origin validation;
- URL protocol allowlist;
- request size limits;
- rate limits for expensive resolve calls;
- output path restrictions;
- subprocess argument arrays;
- filename sanitization;
- secret redaction.

### Security tests

Attempt:

```text
file:///...
../...
data:...
javascript:...
http://127.0.0.1...
arbitrary command strings
```

Expected: rejected or safely handled.

---

# Phase 11 — Native Messaging

## Objectives

Evaluate whether packaged releases should use browser Native Messaging.

### Why

Native Messaging allows a browser extension to communicate with a registered native application process.

Potential architecture:

```text
Extension
 ↓
Native Messaging Host
 ↓
Local service
```

### Decision gate

Do not implement Native Messaging until:

- localhost MVP works;
- extension UX is validated;
- installation/distribution requirements are understood.

---

# Phase 12 — Batch + history

## Features

- multi-URL queue;
- job history;
- retry failed jobs;
- duplicate detection (same normalized URL + same intent + active/queued → return existing);
- job priority (default 0; higher preempts in queue ordering);
- configurable bandwidth limit (settings model reserved);
- desktop notifications on completion/failure (no heavy dependency);
- output-folder rules;
- cleanup policies;
- URL retention policy (7-day default → NULL + SHA-256 hash).

---

# Phase 13 — Media presets

## Presets

```text
Video
Audio
MP3
MP4
WebM
GIF
WebP
No audio
Mobile
WhatsApp sticker
```

The WhatsApp preset must be implemented as a media transformation pipeline, not as a claim that WhatsApp Web can import arbitrary animated stickers.

---

# Phase 14 — Advanced processing

Potential features:

- trim;
- crop;
- resize;
- bitrate control;
- frame-rate conversion;
- codec selection;
- subtitle extraction;
- metadata editing;
- audio normalization.

Each feature needs a separate capability matrix and tests.

---

# Phase 15 — Performance engineering

Measure:

- startup time;
- memory;
- CPU;
- download throughput;
- FFmpeg throughput;
- queue latency;
- UI payload size;
- SQLite performance;
- disk I/O.

Only then tune:

- Granian workers/threads;
- yt-dlp fragment concurrency;
- FFmpeg thread count;
- scheduler concurrency;
- cache behavior.

---

# Phase 16 — Packaging

Target first:

```text
Windows
```

Then:

```text
Linux
macOS
```

The installer should eventually include or reliably provision:

- local service;
- compatible Python/runtime strategy;
- yt-dlp;
- FFmpeg;
- web assets;
- extension instructions.

The release process must respect the licenses of all bundled components.

Target strategy:

```text
Python application
      ↓
PyInstaller onedir
      ↓
Inno Setup installer
```

Bundle FFmpeg/FFprobe/yt-dlp/yt-dlp-ejs/Deno with pinned versions; no runtime Node server; no reliance on user PATH. Ship `THIRD_PARTY_NOTICES.md`. Prefer LGPL-compatible FFmpeg build.

---

# Phase 17 — Release hardening

Before v1:

### Reliability

- crash recovery;
- cancellation;
- retries;
- disk handling;
- orphan process cleanup.

### Security

- localhost authentication;
- strict input validation;
- no arbitrary command execution;
- minimal browser permissions.

### UX

- understandable errors;
- progress;
- history;
- diagnostics.

### Compatibility

- Chromium;
- Firefox;
- Windows;
- public test sources.

---

# Explicitly deferred

Do NOT implement these during MVP unless a concrete requirement appears:

- Redis;
- PostgreSQL;
- Celery;
- Kubernetes;
- Docker-only deployment;
- cloud storage;
- user accounts;
- telemetry;
- AI upscaling;
- remote media processing;
- distributed load balancing.

---

## Resolved decisions (no longer open):

1. Project name: **Local Media Downloader**; repo `local-media-downloader`.
2. Windows packaging: PyInstaller onedir → Inno Setup. No onefile as primary strategy.
3. Third-party binaries: bundled, pinned, with THIRD_PARTY_NOTICES.md; FFmpeg preferably LGPL build.
4. Project license: Apache License 2.0; dependencies keep their own licenses.
5. Native Messaging: not in MVP; localhost + FastAPI is the MVP integration.
6. Extension permissions: `activeTab` + `storage`; no `<all_urls>`, `history`, `cookies`, `webRequest` by default.
7. URL retention: full URL retained 7 days by default, then NULL + SHA-256 hash; configurable; `job_events` never stores full URLs.
8. Dedup rule: same normalized URL + same output intent + active/queued → return existing job.
9. Default output: `Downloads/Local Media Downloader/` via a platform paths layer.
10. App data: Windows app-data, XDG on Linux, Application Support on macOS.
11. GPU: P2; adapters designed so NVENC/AMF/VAAPI/VideoToolbox/Quick Sync can be added without domain changes.
12. Plugins: deferred; extensibility via adapters only.
13. Frontend stack: Svelte 5 + Vite + TypeScript + Tailwind + pnpm.
14. Backend stack: FastAPI + Granian.
15. Python env: uv + `.venv` + `pyproject.toml` + `uv.lock`.
16. Persistence: SQLite only.
17. Scheduler: in-process asyncio, no external broker.
18. Real-time: SSE, not WebSockets.
19. UI delivery: FastAPI serves built static frontend; no separate Node server in production.
20. Type checking: Pyright. Lint/format: Ruff. Tests: pytest + httpx.
21. JS runtimes: Deno only inside the extraction engine (yt-dlp-ejs); pnpm/Node are build-time only.

## Remaining open questions

1. Exact browser permission set beyond `activeTab` + `storage`, per future feature.
2. Whether duplicate jobs are ever auto-merged or only detected-and-returned (currently: return existing).
3. GPU acceleration strategy details (which encoder stack per platform).
4. Whether a future plugin system is worth its complexity.

---

# OpenCode operating rules

OpenCode should:

1. Read all project documentation before changing architecture.
2. Implement only the current phase.
3. Preserve the documented boundaries.
4. Avoid adding infrastructure without a concrete requirement.
5. Add tests with each non-trivial feature.
6. Never replace a documented architectural decision silently.
7. If implementation pressure conflicts with the architecture, stop and explain the conflict.
8. Prefer a small correct change over a broad speculative refactor.
9. Update documentation when a deliberate architectural decision changes.
10. Never hide a failed test, lint error, subprocess error, or security concern.
11. Run the gates in `docs/TESTING.md` after every non-trivial change, in
    order, stopping at the first red gate. Cost-saving models: deterministic
    formatters (`ruff format`, `prettier --write`) may auto-fix; any other red
    gate ends the session with a HANDOFF block (`TESTING.md` §4/§6) — no fix
    loops. A stronger model resolves the handoff next session.
