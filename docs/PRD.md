# PRD — Local Media Downloader

> Project name: **Local Media Downloader** (official working name). Repository: `local-media-downloader`.

## 1. Product overview

**Local Media Downloader** is a local-first, open-source media acquisition and processing tool composed of:

- A browser extension for Chromium-based browsers and Firefox.
- A local desktop service/API running on the user's computer.
- A lightweight web UI for inspecting media and configuring output.
- `yt-dlp` as the primary extractor/downloader engine.
- FFmpeg/FFprobe as the media processing and inspection engine.
- A local job/state store using SQLite.
- A local filesystem workspace for temporary and final media.

The product accepts a media page URL, resolves the media capabilities available for that URL, lets the user select an output intent, downloads the source locally, optionally transforms it, and places the final artifact in a user-selected local directory.

**Core principle:** media bytes should remain on the user's computer. The project must not require a proprietary cloud backend, VPS, remote database, or subscription for its core functionality.

License: Apache License 2.0 for our own code. Third-party components retain their own licenses and are documented in `THIRD_PARTY_NOTICES.md`.

---

## 2. Problem

Existing browser downloaders tend to fall into one or more of these categories:

- They support only a small number of sites.
- They rely on fragile page-specific JavaScript.
- They send URLs/media through a third-party server.
- They provide poor control over quality, codecs, containers, and post-processing.
- They do not recover gracefully from interrupted jobs.
- They mix extraction, downloading, conversion, and UI concerns.

`yt-dlp` already solves a large portion of the difficult extraction problem. The opportunity is to build a professional local orchestration layer around it.

---

## 3. Goals

### G1 — Universal URL entry

The user can send the current page URL from the browser extension to the local application.

The first version should optimize for URLs rather than attempting to detect every `<video>` element on every website.

### G2 — Capability discovery

Given a URL, the application should report:

- title when available;
- thumbnail when available;
- duration when available;
- extractor/site;
- whether the media appears downloadable;
- available video formats;
- available audio formats;
- resolution;
- frame rate when available;
- codecs when available;
- container/extension;
- approximate file size when available;
- HDR/high-frame-rate indicators when available;
- subtitles when supported;
- warnings or limitations.

### G3 — User-controlled output

The user can choose intents such as:

- Best available video + audio.
- Maximum source quality.
- Specific resolution.
- Specific format/container.
- Video only.
- Audio only.
- Extract MP3.
- Convert to MP4.
- Convert to WebM.
- Remove audio.
- Keep original streams when possible.
- Re-encode only when required.
- Resize/downscale.
- Crop.
- Trim.
- Future: GIF/WebP/WhatsApp-compatible sticker preset.

### G4 — Local processing

Downloads and conversions happen locally.

No media file is uploaded to a project-controlled cloud.

The application may communicate with the source website and, optionally, public metadata endpoints required by supported extractors.

### G5 — Reliable jobs

A download/conversion is represented as a durable job.

The system should handle:

- application crash;
- browser crash;
- computer restart;
- temporary network failure;
- source timeout;
- disk-full condition;
- user cancellation;
- FFmpeg failure;
- yt-dlp failure;
- partial output;
- stale jobs;
- duplicate submissions.

### G6 — Resource-aware concurrency

Multiple jobs can be queued, but execution must be bounded by local resources.

The system must avoid starting many FFmpeg encoders simultaneously and exhausting:

- CPU;
- RAM;
- disk I/O;
- network bandwidth;
- GPU resources if GPU acceleration is introduced later.

### G7 — Professional architecture without unnecessary infrastructure

The architecture should be production-quality while remaining appropriate for a single-user local application.

No Redis, PostgreSQL, Kubernetes, cloud load balancer, message broker, or VPS should be required by the default installation.

---

## 4. Non-goals

The following are explicitly out of scope for the initial product:

- A public cloud downloader.
- A hosted service that proxies user media.
- Account management.
- User subscriptions.
- Remote media storage.
- A social-media crawler.
- Circumventing DRM.
- Circumventing paywalls or authentication controls.
- Automated access to private accounts.
- Guaranteed support for every website.
- Guaranteed downloading of protected/DRM media.
- AI video upscaling in the MVP.
- Mobile applications.

The system should clearly report unsupported/protected content rather than attempting unsafe or brittle workarounds.

---

## 5. Target users

### Primary

Developers and technically capable users who want a local open-source media tool.

### Secondary

Users who:

- regularly download public media for legitimate purposes;
- want control over output formats;
- want to avoid uploading media to third parties;
- want browser integration;
- want reproducible local processing pipelines.

---

## 6. Core user journeys

### Journey A — Download current page

1. User opens a supported video page.
2. User clicks the extension.
3. Extension reads the current tab URL.
4. User selects "Open in Local Media Downloader".
5. Web UI opens locally.
6. Application resolves the URL.
7. UI displays available capabilities.
8. User selects an output preset.
9. Job is created.
10. Scheduler starts the job when resources allow.
11. yt-dlp downloads source streams.
12. FFmpeg processes them if required.
13. Final artifact is atomically committed.
14. UI reports completion and local file path (progress is streamed to the UI in real time over SSE during the job).
15. User can open the output folder from the UI (restricted to application-managed paths).

### Journey B — Paste URL

1. User opens local web UI.
2. User pastes a URL.
3. User clicks Resolve.
4. Same resolution flow as Journey A.

### Journey C — Batch queue

1. User submits several URLs.
2. Each URL becomes an independent job.
3. Scheduler applies concurrency limits.
4. Jobs progress independently.
5. Failed jobs remain visible and can be retried.
6. Completed jobs remain in history until retention cleanup.

### Journey D — Interrupted computer

1. User starts a download.
2. Computer loses power.
3. Application stops unexpectedly.
4. On next startup, the recovery scanner finds unfinished jobs.
5. Job state is reconciled with filesystem/process state.
6. Job is marked resumable, retryable, or failed.
7. User can resume without losing completed work where the downloader supports resumption.

---

## 7. Feature requirements

### P0 — MVP

- Local API/service.
- Browser extension.
- URL submission.
- URL resolution.
- yt-dlp integration.
- Format discovery.
- Best-quality download.
- Audio extraction.
- MP3 output.
- MP4 output.
- WebM output where supported.
- Remove audio.
- Basic resizing/downscaling.
- Job queue.
- Progress.
- Cancellation.
- Retry.
- Persistent job state.
- Crash/restart recovery.
- Local-only media storage.
- Disk-space checks.
- Safe temporary files.
- Structured logs.
- Extension-to-local-service authentication.
- Extension service health indicator.
- Open output folder action.
- Windows support first.

### Data retention and deduplication

- Different output intents for the same URL are distinct jobs.
- A job is considered a duplicate when another active/queued job has the same normalized URL AND the same output intent. Duplicates return the existing job.
- The full `source_url` is retained for 7 days by default, then replaced by `NULL` plus a SHA-256 `source_url_hash`. Retention is configurable.
- `job_events` must not store full URLs.
- No cookies or credentials are stored by default.

### P1

- Firefox support.
- macOS/Linux support.
- Batch downloads.
- Download history.
- Presets.
- Trim by time range.
- GIF/WebP output.
- Subtitle download.
- Metadata export.
- Automatic output-folder organization.
- Native Messaging integration.
- Better capability diagnostics.
- Import/export configuration.
- Configurable bandwidth limit.
- Desktop notifications on job completion/failure.
- Job priority in the queue.

### P2

- Hardware acceleration detection.
- GPU-aware encoding.
- AI upscaling as an optional external pipeline.
- Advanced filters.
- Watch folders.
- Plugin/extractor adapters.
- Advanced automation.

---

## 8. Quality semantics

### "Best available"

Select the best downloadable source quality exposed by the extractor.

### "Maximum source quality"

Equivalent to the highest source quality that can actually be obtained and processed.

### "Upscale"

Means increasing output dimensions beyond the source.

This is NOT the same as obtaining higher-quality source media.

The MVP must not claim that an upscale creates missing detail.

AI upscaling is a separate future capability.

---

## 9. Local storage policy

The project must never store downloaded media inside SQLite.

SQLite stores metadata/state only.

Suggested local structure:

```text
data/
├── app.db
├── jobs/
│   └── <job-id>/
│       ├── job.json
│       ├── source/
│       ├── work/
│       ├── output/
│       └── logs/
├── cache/
└── logs/
```

The exact layout can evolve, but temporary and final artifacts must be clearly separated.

Final files should be written to temporary names and atomically renamed/moved only after successful validation.

Default user output root: `Downloads/Local Media Downloader/`. Default application data/cache/config use platform-standard locations (Windows app-data locations, XDG on Linux, Application Support/Cache on macOS). A paths/platform layer owns these decisions; no hardcoded `C:\Users\...` strings in feature code.

---

## 10. Privacy

The application should default to:

- localhost-only binding;
- no telemetry;
- no account;
- no remote database;
- no remote media proxy;
- no automatic cookie collection;
- no browser history collection;
- minimal URL retention;
- configurable job-history retention.

If future features require cookies, permissions must be explicit and narrowly scoped.

---

## 11. Security

The local service must not become an arbitrary localhost command-execution endpoint.

Requirements:

- bind to loopback only by default;
- require an application-generated authentication token for extension/API requests;
- validate Origin/extension identity where possible;
- validate URLs;
- reject unsupported protocols such as `file:`, `javascript:`, `data:` and arbitrary local-resource schemes;
- never pass user input directly into a shell command;
- invoke subprocesses using argument arrays;
- constrain output paths;
- prevent path traversal;
- enforce resource limits;
- sanitize filenames;
- do not expose arbitrary filesystem read/write APIs;
- do not expose arbitrary command execution;
- redact secrets from logs.

---

## 12. Success criteria

The MVP is successful when a user can install the application, open a supported public video page, click the extension, choose a format, download it locally, and recover gracefully after interruption.

The product should feel like a local desktop application even though its UI is a browser-based Svelte application served by the local service.

---

## 13. Constraints and legal/ethical boundary

The tool is an open-source media utility. Users are responsible for complying with the terms of the source website, copyright law, privacy law, and applicable access restrictions.

The project should not market itself as a DRM circumvention tool.

Extractor limitations must be treated as normal technical limitations rather than problems that justify bypassing access controls.

A future explicit, opt-in cookies capability may be added for sources that require user authentication. Cookies are never collected globally or silently.
