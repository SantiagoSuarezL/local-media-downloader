# Technical Specification — Local Media Downloader

## 1. Technology baseline

### Backend

- Python 3.12+ (exact supported version pinned in project metadata)
- uv
- `.venv`
- FastAPI
- Granian
- Pydantic
- SQLite via Python's standard library where practical
- pytest
- Ruff (lint + formatting)
- Pyright (type checking)
- structured logging

`uv` owns Python dependency resolution and the project environment.

### Media

- yt-dlp
- yt-dlp-ejs
- Deno (dedicated JS runtime for yt-dlp-ejs)
- FFmpeg
- FFprobe

The application must verify that required binaries exist and report their versions.

`yt-dlp-ejs` plus a dedicated JavaScript runtime (Deno) are part of the extraction engine because of the current yt-dlp ecosystem requirements.

Deno is an internal dependency of the extraction engine only. It is NOT a frontend runtime and does not replace pnpm or Node build tooling. It must not appear as a second frontend stack.

### yt-dlp integration strategy

- yt-dlp is a versioned Python dependency in the uv environment.
- Extraction is encapsulated behind an `Extractor` adapter.
- The domain never depends on yt-dlp's raw JSON schema; an adapter normalizes it into `MediaInfo`.
- The yt-dlp CLI surface is never exposed directly to the API.
- Execution uses controlled subprocesses where isolation is needed; argument arrays, no shell strings.
- Diagnostics must report the installed yt-dlp version and a clear signal when it may be outdated (extractors break when platforms change).
- No automatic self-updater by default. Updates are a controlled, explicit action.

### Frontend

- Svelte 5
- Vite
- TypeScript
- Tailwind CSS
- pnpm (single JS/TS package manager)
- no SSR framework
- no separate Node server at runtime

The frontend is built to static assets. FastAPI serves those assets in production.

Node/pnpm/Vite are used for development, build, lint, and test only.

### Extension

- TypeScript
- Manifest V3-compatible architecture
- browser API compatibility layer
- service worker
- popup/options pages
- Vite or another minimal bundler if needed

Do not force the extension to use the dashboard framework.

---

## 2. Repository layout

Recommended monorepo:

```text
local-media-downloader/
├── apps/
│   ├── api/
│   │   ├── src/
│   │   ├── tests/
│   │   └── pyproject.toml
│   ├── web/
│   │   ├── src/
│   │   └── package.json
│   └── extension/
│       ├── src/
│       └── package.json
├── packages/
│   └── contracts/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── TECHNICAL_SPEC.md
│   ├── ENGINEERING_PRINCIPLES.md
│   └── IMPLEMENTATION_PLAN.md
├── data/
├── pyproject.toml
├── uv.lock
├── pnpm-workspace.yaml
└── README.md
```

The exact structure may change if implementation reveals a better boundary.

---

## 3. API contract

Version API routes:

```text
/api/v1/health
/api/v1/resolve
/api/v1/jobs
/api/v1/jobs/{job_id}
/api/v1/jobs/{job_id}/cancel
/api/v1/jobs/{job_id}/retry
/api/v1/jobs/{job_id}/file
/api/v1/events
/api/v1/settings
```

### Health

```http
GET /api/v1/health
```

Response should expose:

- application version;
- API status;
- yt-dlp availability/version;
- FFmpeg availability/version;
- FFprobe availability/version;
- database status;
- storage status.

Do not expose sensitive filesystem information.

### Events

```http
GET /api/v1/events
Accept: text/event-stream
```

Server-Sent Events stream of normalized progress and scheduler events:

```text
state
stage
percentage
downloaded_bytes
total_bytes
speed_bytes_per_second
eta_seconds
current_file
error_code
```

The UI must not parse raw yt-dlp/FFmpeg stdout as its primary progress protocol.

### Resolve

```http
POST /api/v1/resolve
Content-Type: application/json
```

Request:

```json
{
  "url": "https://example.com/video"
}
```

Response concept:

```json
{
  "resolution_id": "uuid",
  "source": {
    "url": "https://example.com/video",
    "extractor": "example",
    "title": "Example"
  },
  "media": {
    "duration_seconds": 123,
    "thumbnail_url": "...",
    "is_live": false
  },
  "formats": [],
  "capabilities": [],
  "warnings": []
}
```

Never return raw extractor internals as the only API contract. Normalize them.

---

## 4. Format model

A normalized format should contain fields such as:

```text
id
kind: video | audio | combined
container
extension
video_codec
audio_codec
width
height
fps
bitrate
audio_bitrate
filesize
filesize_approx
dynamic_range
protocol
has_video
has_audio
quality_score
```

Not every source provides every field.

Use `null` rather than fake values.

---

## 5. Output intent model

Do not let the UI construct arbitrary yt-dlp/FFmpeg command lines.

Represent user intent:

```json
{
  "media": "video",
  "quality": "best",
  "container": "mp4",
  "audio": "include",
  "video_codec": "source",
  "processing": {
    "resize": null,
    "trim": null
  }
}
```

The backend maps this intent to an internal execution plan.

This prevents the API from becoming a command-execution interface.

---

## 6. Execution plan

Example:

```text
OutputIntent
      ↓
Planner
      ↓
ExecutionPlan
      ├── extraction
      ├── download
      ├── merge
      ├── transcode
      ├── postprocess
      └── validation
```

Example best MP4:

```text
1. resolve
2. select best compatible video/audio
3. download
4. merge if required
5. remux/transcode only if necessary
6. ffprobe validation
7. atomic finalization
```

Example MP3:

```text
1. resolve
2. select best audio
3. download
4. FFmpeg audio conversion
5. metadata handling
6. validation
7. atomic finalization
```

Example remove audio:

```text
1. resolve/download video
2. stream-copy video if compatible
3. discard audio
4. validate
5. finalize
```

Avoid transcoding when stream-copy can satisfy the requested output.

---

## 7. "Maximum quality"

The system must never manufacture a fake "maximum quality".

Source maximum means:

```text
highest usable source representation
```

If the source is 720p, exporting a 1080p file without an upscale is not 1080p quality.

If the user requests a larger resolution, classify it as:

```text
UPSCALE
```

and make the UI explicit.

---

## 8. Upscaling strategy

MVP:

- no AI upscaling;
- allow only source-preserving selection and conventional resizing/downscaling.

Future:

- FFmpeg scaler for conventional resizing;
- optional GPU encoders;
- optional external AI upscaler.

AI upscaling must be a separate pipeline because it changes resource requirements dramatically.

---

## 9. Job persistence

SQLite schema concept:

### jobs

```text
id
created_at
updated_at
state
source_url            -- retained ~7 days by default, then NULL
source_url_hash       -- SHA-256 of the source URL, kept after retention expiry
extractor
title
intent_json
execution_plan_json
progress
bytes_downloaded
total_bytes
current_stage
attempt_count
error_code
error_message
output_path
created_by
priority              -- default 0 (normal); higher preempts in queue ordering
```

### job_events

```text
id
job_id
timestamp
event_type
payload_json
```

`payload_json` must not contain full source URLs; use `source_url_hash` or redacted references.

### settings

```text
key
value_json
updated_at
```

Known keys (examples):

```text
max_total_jobs = 3
max_download_jobs = 2
max_encode_jobs = 1
min_free_disk_gb
bandwidth_limit_bps     (nullable; future/configurable)
source_url_retention    (immediately | 7 days | 30 days | never)
history_retention_days
temporary_retention_hours
default_output_root     (Downloads/Local Media Downloader/)
```

Do not store large media payloads.

### Event retention

`job_events.payload_json` must not grow indefinitely.

Policy:

- retain events for a bounded period (default: configurable, e.g. 30 days);
- cap payload size per event;
- compact events for terminal jobs older than the retention window;
- never let event history block job state transitions.

The state row in `jobs` is the source of truth; `job_events` is diagnostic/audit detail.

---

## 10. SQLite configuration

Use:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

Use transactions for state transitions.

For normal operation, a balanced synchronous setting may be used after testing. If maximum durability is preferred for critical state, use a stricter synchronous configuration.

The application must never assume a database commit means that a media file is valid. File validation is a separate responsibility.

---

## 11. Filesystem safety

Use per-job directories:

```text
data/jobs/<job-id>/
├── source/
├── work/
├── output/
└── logs/
```

Rules:

- never write final output directly to its final filename;
- write to a temporary filename;
- validate;
- atomically rename/move;
- sanitize user-visible names;
- never allow `../`;
- never accept arbitrary absolute paths from API requests;
- only allow configured output roots.

---

## 12. Recovery

At application startup:

1. Open SQLite.
2. Find jobs in active states.
3. Verify whether worker processes are actually alive.
4. Mark orphaned execution attempts as interrupted.
5. Inspect temporary artifacts.
6. Determine whether the job is resumable.
7. If resumable, move to `QUEUED` or `RETRY_WAIT`.
8. If unsafe/ambiguous, mark `RECOVERY_REQUIRED`.
9. Never silently overwrite a completed final file.

A job must be idempotent where practical.

---

## 13. Power failure

Scenario:

```text
computer power loss
        ↓
process disappears
        ↓
partial files remain
        ↓
startup recovery
        ↓
SQLite says DOWNLOADING
        ↓
no active PID
        ↓
mark INTERRUPTED
        ↓
retry/resume
```

The downloader may be able to resume an incomplete download depending on the source/protocol.

If resumption is unavailable, the system should restart the download safely.

Partial artifacts must never be presented as completed output.

---

## 14. Progress

The API should expose normalized progress:

```text
state
stage
percentage
downloaded_bytes
total_bytes
speed_bytes_per_second
eta_seconds
current_file
```

Stages:

```text
resolving
queued
downloading
merging
processing
validating
finalizing
completed
```

Do not expose raw yt-dlp/FFmpeg output as the UI's primary progress protocol.

Raw logs remain available for diagnostics.

---

## 15. Cancellation

Cancellation is cooperative first:

1. mark job as cancellation requested;
2. terminate child process gracefully;
3. wait bounded period;
4. force terminate process tree if necessary;
5. clean temporary artifacts;
6. set `CANCELLED`.

The system must avoid orphaned FFmpeg/yt-dlp processes.

---

## 16. Retry policy

Retry categories:

### Retryable

- network timeout;
- transient connection failure;
- temporary source failure;
- temporary filesystem lock;
- recoverable fragment failure.

### Non-retryable

- unsupported URL;
- DRM/protected content;
- invalid user configuration;
- insufficient permissions;
- invalid output configuration.

### Resource retry

- disk full;
- insufficient RAM;
- concurrency limit.

These should not blindly retry. The system should wait for a resource condition to improve.

---

## 17. Concurrency

Initial defaults should be conservative.

Example policy:

```text
max_total_jobs = 3
max_download_jobs = 2
max_encode_jobs = 1
```

These are configurable and should be adapted later based on CPU/RAM/storage.

The scheduler must treat FFmpeg encoding as more resource-intensive than metadata resolution.

The baseline scheduler is implemented with Python `asyncio`.

Do not add Celery, RQ, Redis, Kafka, or an external queue unless a concrete requirement appears.

`watchfiles` is not used at runtime; use it only for development hot reload if needed.

---

## 18. Disk management

Before starting a job:

- determine estimated/known source size when available;
- reserve a safety margin;
- check free disk space;
- account for intermediate files;
- account for output file;
- reject jobs when insufficient space is obvious.

After completion:

- retain final output;
- remove temporary artifacts;
- optionally compact old job records.

Future setting:

```text
minimum_free_disk_gb
temporary_retention_hours
history_retention_days
```

---

## 19. Networking

The application is local, but yt-dlp communicates with source services.

Requirements:

- configurable timeout;
- retries;
- exponential backoff where appropriate;
- user-agent behavior delegated to extractor where possible;
- no uncontrolled proxying;
- optional proxy configuration in future;
- clear errors for rate limits and anti-bot failures.

Do not promise that all source sites will work.

yt-dlp's extractor ecosystem changes over time, and some platforms can impose additional requirements or tokens.

---

## 20. Extension API

Extension should send:

```json
{
  "url": "https://example.com/video",
  "source": "browser_action"
}
```

The service returns a short-lived handoff identifier or opens the local UI.

Do not place full job logic in the popup.

The popup should be intentionally small.

Suggested actions:

```text
[ Resolve current page ]
[ Open dashboard ]
[ Service status ]
```

---

## 21. Authentication

Generate a random local secret during first-run setup.

Store it securely according to platform capabilities.

Requests must include:

```text
Authorization: Bearer <local-token>
```

or an equivalent mechanism.

The token is local-only.

Never hardcode a universal token.

---

## 22. Browser extension security

The extension service worker must validate incoming messages and sender information before forwarding requests.

Do not accept arbitrary webpage messages as privileged commands.

Content scripts must not directly communicate with native processes.

If Native Messaging is used, only the extension service worker/background context should interact with the native host.

Manifest permissions follow the minimal-permission principle:

```text
activeTab
storage
```

Host access to localhost is requested only when actually needed. Do NOT request by default:

```text
<all_urls>
history
cookies
webRequest
```

Native Messaging is not required for the MVP; it is a future packaging/integration improvement.

---

## 23. Observability

Use structured logs:

```text
timestamp
level
component
job_id
event
duration_ms
error_code
```

Logs must never contain:

- authentication tokens;
- cookies;
- authorization headers;
- raw secrets.

URLs may be considered sensitive and should be configurable for redaction.

---

## 24. Testing requirements

### Unit

- URL validation;
- format normalization;
- planner;
- state machine;
- retry classification;
- filename sanitization;
- disk-space policy.

Tooling:

- Ruff for lint + formatting;
- Pyright for type checking;
- pytest for tests;
- httpx / FastAPI test client for API tests;
- pytest-asyncio only where async tests genuinely require it.

Frontend:

- Svelte component/unit tests where justified;
- integration tests for state;
- end-to-end tests for critical flows;
- do not add a heavy testing framework by default.

### Integration

- yt-dlp invocation;
- FFmpeg invocation;
- SQLite persistence;
- recovery;
- cancellation;
- output validation.

### End-to-end

```text
extension
 → local API
 → resolve
 → create job
 → download
 → process
 → validate
 → final file
```

Use test fixtures and permitted/public test media.

---

## 25. Dependency policy

Every dependency must have a reason.

Avoid:

- ORM when direct SQLite is sufficient;
- Redis;
- Celery/RQ;
- Docker requirement for local users;
- React/Next.js;
- a frontend state library;
- a remote database;
- telemetry SDKs.

Add infrastructure only when a concrete requirement appears.

---

## 26. Packaging

Windows is the first target platform.

Target strategy:

```text
Python application
      ↓
PyInstaller (onedir bundle; NOT onefile as primary strategy)
      ↓
Inno Setup
      ↓
Windows installer
```

The installed application must work without the user manually installing:

```text
Python, FFmpeg, FFprobe, yt-dlp, Deno, Node.js
```

Third-party binaries are bundled/provisioned reproducibly with exact pinned versions. The application must not rely on the user's global PATH.

No silent downloading of critical components on first run.

Each release must ship:

```text
THIRD_PARTY_NOTICES.md
```

and a licenses document. FFmpeg must use a license-compatible build for our distribution strategy — preferably an LGPL build when sufficient. Do not assume any `ffmpeg.exe` found online is redistributable.

Project license: Apache License 2.0 for our own code. Third-party components retain their own licenses. Do not mix dependency licenses with the project license.

Do not decide PyInstaller vs Nuitka etc. until the packaging phase evaluates them; PyInstaller + Inno Setup is the current default plan and must not force a runtime stack change.
