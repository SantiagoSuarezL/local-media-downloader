# Architecture — Local Media Downloader

## 1. Architectural style

Local Media Downloader uses a **local-first modular monolith with a durable job scheduler**.

It is not a distributed cloud system.

The architecture deliberately avoids introducing distributed infrastructure where a single computer does not need it.

```text
┌──────────────────────────────────────────────────────────────┐
│                         User Computer                         │
│                                                              │
│  ┌───────────────┐        ┌───────────────────────────────┐  │
│  │ Browser        │        │ Local Application             │  │
│  │ Extension      │───────▶│                               │  │
│  │ MV3            │        │ Svelte UI (static assets)                    │  │
│  └───────────────┘        │       │                       │  │
│                            │       ▼                       │  │
│                            │ FastAPI + Granian             │  │
│                            │       │                       │  │
│                            │       ▼                       │  │
│                            │ Job Manager / Scheduler       │  │
│                            │       │                       │  │
│                            │       ▼                       │  │
│                            │ Worker Pool                   │  │
│                            │   │        │                  │  │
│                            │   ▼        ▼                  │  │
│                            │ yt-dlp   FFmpeg/FFprobe        │  │
│                            │   │        │                  │  │
│                            │   └────┬───┘                  │  │
│                            │        ▼                      │  │
│                            │ Local filesystem + SQLite      │  │
│                            └───────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Why not a cloud architecture?

The product requirement is local processing.

A cloud architecture would introduce:

- server bandwidth costs;
- storage costs;
- privacy concerns;
- authentication;
- remote job queues;
- scaling;
- abuse prevention;
- rate limiting;
- media retention;
- legal/data-handling complexity.

Those are unnecessary for the core use case.

---

## 3. Why not a traditional load balancer?

A network load balancer solves a distributed-service problem.

This application has one local host.

Instead, the architecture uses:

```text
HTTP concurrency
      +
durable job queue
      +
resource-aware worker pool
      +
per-operation limits
```

The scheduler is the local equivalent of workload balancing.

If the project later gains a hosted mode, a remote deployment can introduce:

```text
Reverse proxy
      ↓
API replicas
      ↓
Redis / queue
      ↓
worker fleet
      ↓
object storage
```

That architecture must remain optional and must not leak into the local MVP.

---

## 4. Runtime components

### 4.1 Browser extension

Responsibilities:

- identify current tab URL;
- allow explicit URL submission;
- send URL to local app;
- open local UI;
- optionally show local-service status;
- optionally monitor jobs;
- avoid extracting media itself.

The extension should remain thin.

It must not contain platform-specific extraction logic.

### 4.2 Svelte web UI

Responsibilities:

- media resolution UI;
- format selection;
- preset selection;
- job list;
- progress;
- settings;
- diagnostics.

The frontend uses Svelte 5 + Vite + TypeScript + Tailwind CSS, compiled to static assets.

In production, FastAPI serves those built assets. There is no mandatory Node.js server at runtime; Node/pnpm/Vite are build-time and development tooling only.

Real-time job progress is delivered to the UI over Server-Sent Events (SSE). User-initiated actions use plain HTTP.

Svelte 5's native reactivity (`$state`, `$derived`, `$effect`) is the default state model. External global state libraries (Redux, Zustand, Pinia, etc.) are not used unless a concrete documented need appears.

Avoid introducing React, Next.js, Remix, SvelteKit, or an SSR server unless a future explicit architectural decision justifies it.

### 4.3 FastAPI API

Responsibilities:

- API boundary;
- authentication;
- request validation;
- capability resolution;
- job creation;
- job status;
- cancellation;
- configuration;
- health/readiness endpoints;
- SSE event stream for progress and scheduler events;
- serving built frontend static assets in production.

FastAPI must not perform long-running media operations directly inside request handlers.

### 4.4 Granian

Granian is the HTTP/ASGI server.

Initial local configuration should prefer a single API worker because the application is local and the durable scheduler owns job execution.

Multiple Granian workers may be considered later, but only after the API has no process-local state assumptions.

### 4.5 Job manager

The job manager owns:

- state transitions;
- queue ordering;
- retry policy;
- cancellation;
- startup recovery;
- stale-job detection;
- worker assignment;
- resource limits.

### 4.6 Worker

A worker owns one media operation at a time.

The worker should invoke external tools:

```text
yt-dlp       (+ yt-dlp-ejs via a dedicated Deno runtime)
FFmpeg
FFprobe
```

It should not expose shell access to the API.

Deno is used only as the extraction engine's JS runtime; it is not a frontend or server runtime.

### 4.7 SQLite

SQLite stores:

- job metadata;
- state;
- timestamps;
- selected preset;
- source URL;
- extractor metadata;
- retry count;
- error category;
- final output path;
- checksums where useful;
- application configuration that benefits from structured persistence.

SQLite does NOT store:

- video bytes;
- audio bytes;
- thumbnails as blobs;
- arbitrary downloaded content.

Use WAL mode and transactions.

### 4.8 Filesystem

Filesystem stores:

- temporary downloads;
- intermediate files;
- final output;
- logs;
- optional cached metadata.

---

## 5. Job lifecycle

```text
CREATED
  │
  ▼
RESOLVING
  │
  ├── failed ───────────────▶ FAILED
  │
  ▼
READY
  │
  ▼
QUEUED
  │
  ▼
DOWNLOADING
  │
  ├── cancelled ────────────▶ CANCELLED
  ├── retryable error ──────▶ RETRY_WAIT
  └── success
          │
          ▼
PROCESSING
  │
  ├── no processing required
  │
  ▼
VALIDATING
  │
  ├── invalid ──────────────▶ FAILED
  │
  ▼
COMMITTING
  │
  ▼
COMPLETED
```

Recovery states:

```text
DOWNLOADING
PROCESSING
COMMITTING
```

may be found after startup.

They must not be assumed to still have an active process.

The recovery subsystem reconciles database state and filesystem state.

---

## 6. Data flow

### Resolve

```text
Extension/UI
    ↓
POST /api/v1/resolve
    ↓
FastAPI validation
    ↓
Resolution service
    ↓
yt-dlp metadata extraction
    ↓
normalized MediaInfo
    ↓
UI
```

### Download

```text
UI
 ↓
POST /api/v1/jobs
 ↓
SQLite transaction
 ↓
QUEUED
 ↓
Scheduler
 ↓
Worker
 ↓
yt-dlp
 ↓
source artifact
 ↓
FFmpeg if needed
 ↓
FFprobe validation
 ↓
atomic finalization
 ↓
COMPLETED
```

---

## 7. Resource-aware scheduler

The scheduler must not use an unlimited async task pool.

A job has resource characteristics:

```text
network-heavy
cpu-heavy
disk-heavy
gpu-heavy
```

Examples:

- direct download: network-heavy;
- MP3 extraction from downloaded source: CPU-light/medium;
- H.264 re-encode: CPU-heavy;
- AI upscale: GPU/CPU-heavy.

The scheduler should enforce:

```text
max_active_downloads
max_active_encoders
max_active_total_jobs
max_disk_usage
min_free_disk_space
```

Later it may estimate job cost from source duration/resolution/codec.

---

## 8. Process isolation

Each external operation is a subprocess.

The worker must:

- create a controlled working directory;
- pass explicit arguments;
- capture stdout/stderr;
- track PID/process group;
- support cancellation;
- enforce timeouts where appropriate;
- terminate child processes on cancellation;
- record exit code;
- parse structured progress when possible.

No shell string interpolation.

---

## 9. Extension communication

### Phase 1 — localhost

```text
Extension
    ↓
http://127.0.0.1:<port>
    ↓
FastAPI
```

The extension sends an application-generated token.

The service binds only to loopback.

### Real-time channel

Progress and scheduler events are pushed to the UI over SSE:

```text
Job Manager / Scheduler
        ↓
GET /api/v1/events (SSE)
        ↓
Svelte UI
```

WebSockets are not used for the MVP. Plain HTTP is used for user actions (create, cancel, retry).

### Phase 2 — Native Messaging

For packaged releases, consider:

```text
Extension
    ↓
Browser Native Messaging
    ↓
Native host
    ↓
Local service
```

This can reduce the attack surface of an exposed localhost HTTP API and improve installation/discovery.

---

## 10. Browser compatibility

Target:

- Chromium Manifest V3.
- Firefox WebExtensions.

Keep browser-specific APIs behind a thin adapter:

```text
browser/
├── chrome/
└── firefox/
```

The core extension logic should not know which browser it runs in.

---

## 11. Security boundaries

Trust zones:

```text
UNTRUSTED
web pages / URLs
       │
       ▼
extension
       │
validated authenticated request
       ▼
LOCAL API
       │
validated job specification
       ▼
WORKER
       │
explicit subprocess arguments
       ▼
yt-dlp / FFmpeg
```

A webpage must never be able to turn the service into arbitrary command execution.

---

## 12. Future hosted architecture

If a hosted version is ever desired, it should be a separate deployment profile:

```text
Browser
  ↓
CDN / reverse proxy
  ↓
API
  ↓
Queue
  ↓
Workers
  ↓
Object storage
```

The local architecture should not depend on any of those services.
