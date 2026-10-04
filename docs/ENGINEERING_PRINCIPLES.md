# Engineering Principles — Local Media Downloader

## 1. Local-first is an architectural constraint

The default application must work without:

- an account;
- a VPS;
- a cloud database;
- a cloud storage bucket;
- Redis;
- a subscription.

If a feature requires a remote service, it is an optional feature, not a core dependency.

---

## 2. Prefer boring infrastructure

Use the simplest component that satisfies the requirement.

Examples:

```text
SQLite > PostgreSQL
in-process scheduler > Redis queue
filesystem > object storage
FastAPI > distributed API gateway
Granian > multiple application servers
```

Complexity must be earned by a real requirement.

---

## 3. Separate concerns aggressively

The following layers must remain independent:

```text
API
 ↓
Application services
 ↓
Domain/job model
 ↓
Scheduler
 ↓
Execution adapters
 ↓
External tools
```

The API must not contain yt-dlp command construction.

The UI must not know yt-dlp syntax.

The scheduler must not know browser APIs.

The extension must not know media extraction rules.

---

## 4. User intent over command syntax

Never expose arbitrary command lines as the product's primary abstraction.

User says:

> MP4, best available quality, audio included.

The planner decides how to accomplish that.

This protects the architecture from becoming a thin unsafe shell wrapper.

---

## 5. Prefer stream copy over transcoding

If the requested result can be produced by remuxing or stream copying, do that.

Transcoding is slower, consumes more power, and can reduce quality.

Use FFmpeg transcoding only when required by:

- codec incompatibility;
- container restrictions;
- resizing;
- filtering;
- audio conversion;
- explicit user choice.

---

## 6. Never confuse source quality with upscaling

A 1080p output generated from a 720p source is not equivalent to downloading a native 1080p source.

The UI and internal models must distinguish:

```text
native_source_quality
output_dimensions
upscaled
```

---

## 7. External tools are untrusted processes

Treat yt-dlp and FFmpeg as external dependencies.

Capture:

- command version;
- exit code;
- stdout/stderr;
- duration;
- produced files.

Never assume successful process exit means valid output.

Validate with FFprobe or equivalent checks.

---

## 8. No shell interpolation

Bad:

```text
shell("ffmpeg -i " + user_input)
```

Good architecture:

```text
subprocess(
    executable="ffmpeg",
    args=[...validated arguments...]
)
```

User-controlled strings must never become executable shell syntax.

---

## 9. Every long operation is a job

Never perform:

```text
POST /download
→ block HTTP request for 20 minutes
```

Instead:

```text
POST /jobs
→ job_id
→ scheduler
→ worker
→ progress
```

The HTTP API should remain responsive regardless of media workload.

---

## 10. Durable state beats in-memory state

If a process can crash, its important state belongs in persistent storage.

Do not rely on:

```python
active_jobs = {}
```

as the source of truth.

In-memory state may be a cache, never the authoritative job state.

---

## 11. Design for restart

Assume:

- application crashes;
- browser crashes;
- computer restarts;
- power is lost;
- network disappears;
- disk becomes full.

Every state transition must have a sensible recovery behavior.

---

## 12. Atomic finalization

Never expose an incomplete file as completed.

Pattern:

```text
temporary file
    ↓
validation
    ↓
atomic rename
    ↓
completed state
```

The completed database state should only be committed after the output is valid.

---

## 13. Idempotency

Repeated requests should not accidentally create corrupted output.

Where possible:

```text
same job + same intent
→ deterministic execution
```

Duplicate submissions may either:

- create separate jobs intentionally; or
- be detected and offered as duplicates.

The behavior must be explicit.

---

## 14. Resource awareness

A local computer is the infrastructure.

CPU, RAM, disk, network, and GPU are finite.

Do not optimize for theoretical throughput at the expense of the user's machine.

Prefer:

```text
stable + responsive
```

over:

```text
maximum concurrent processes
```

---

## 15. Backpressure everywhere

Backpressure should exist at multiple levels:

```text
HTTP requests
↓
job creation
↓
queue
↓
worker pool
↓
yt-dlp fragments
↓
FFmpeg threads
```

Do not multiply concurrency at every layer.

---

## 16. Fail explicitly

An unsupported URL should produce:

```text
UNSUPPORTED_SOURCE
```

not:

```text
UNKNOWN_ERROR
```

An insufficient disk should produce:

```text
INSUFFICIENT_DISK
```

not:

```text
DOWNLOAD_FAILED
```

Error categories are part of the UX.

---

## 17. No fake capability

Never show an option simply because FFmpeg can technically encode it.

A capability is valid only when:

1. the source can be obtained;
2. the requested transformation is technically valid;
3. the local environment has the required encoder/tool;
4. the resulting file can be validated.

---

## 18. Security by default

The local API is still a security boundary.

Do not assume:

> localhost means trusted.

A malicious webpage or local process may attempt to interact with the service.

Use:

- loopback binding;
- authentication;
- origin validation;
- strict schemas;
- protocol allowlists;
- output-path restrictions;
- subprocess argument arrays;
- resource limits.

---

## 19. Minimal permissions

The browser extension should request the minimum permissions necessary.

Do not request:

```text
<all websites>
cookies
history
tabs
downloads
native messaging
```

unless the feature genuinely requires each permission.

Permissions should be justified individually.

---

## 20. Privacy by architecture

The easiest privacy policy is one enforced by architecture.

Prefer:

```text
URL → local service → local file
```

over:

```text
URL → cloud → remote download → cloud storage → local download
```

Do not collect telemetry by default.

---

## 21. Make failures diagnosable

Every failed job should answer:

- What stage failed?
- Which component failed?
- What exit code occurred?
- Is it retryable?
- What can the user do?
- Where are diagnostic logs?

A generic stack trace is not a user-facing error.

---

## 22. Keep UI fast

Svelte should render with minimal JavaScript and use its native runes (`$state`, `$derived`, `$effect`) for reactivity.

Hydrate only:

- URL submission;
- format selector;
- job controls;
- progress;
- settings where required.

Do not turn the entire UI into a client-side SPA without evidence that it is necessary.

Prefer SSE over WebSockets for server-to-client events.

Do not add a runtime Node.js server when FastAPI can serve the built static assets.

---

## 23. Do not over-engineer for hypothetical scale

Do not add:

- Kubernetes;
- service mesh;
- distributed tracing;
- Redis;
- Kafka;
- remote object storage;
- multiple API replicas;

for a local desktop application.

Design boundaries so these could be added later, but do not implement them prematurely.

---

## 24. Prefer replaceable adapters

External dependencies should be behind adapters:

```text
Extractor
  └── YtDlpExtractor

MediaProcessor
  └── FFmpegProcessor

MetadataInspector
  └── FFprobeInspector

BrowserBridge
  ├── ChromiumBridge
  └── FirefoxBridge
```

This makes future replacement possible without rewriting the domain layer.

---

## 25. Reproducibility

Pin:

- Python version;
- Python dependencies;
- frontend dependencies;
- yt-dlp release;
- FFmpeg release/build where practical.

Record versions in diagnostics.

A user's successful result should be reproducible from the application version and job intent.

---

## 26. Optimize after measuring

Optimization priorities:

1. avoid unnecessary work;
2. avoid unnecessary transcoding;
3. avoid unnecessary memory copies;
4. limit concurrency;
5. use efficient filesystem operations;
6. measure CPU/RAM/disk/network;
7. optimize bottlenecks.

Do not add complexity because a benchmark might improve.

---

## 27. Open-source quality

Every major architectural decision should be explainable.

Prefer:

- small modules;
- clear interfaces;
- strong types;
- tests;
- deterministic behavior;
- documented limitations;
- explicit licensing;
- reproducible development environment.

---

## 28. Definition of done

A feature is not complete merely because the happy path works.

For every feature, verify:

- success;
- invalid input;
- cancellation;
- timeout;
- restart;
- disk full;
- network failure;
- subprocess failure;
- duplicate request;
- malformed metadata;
- unsupported capability;
- security boundary;
- logs;
- tests.

---

## 29. Frontend simplicity

The UI is an interactive local dashboard, not a marketing site and not a distributed app.

Use Svelte 5 + Vite + TypeScript + Tailwind. Do not add SvelteKit, React, Next.js, or a server runtime unless a concrete requirement forces it.

---

## 30. No duplicated server runtime

FastAPI + Granian is the only HTTP server. The frontend is built to static assets and served by FastAPI in production.

Node/pnpm/Vite are build-time and development tooling, not a production dependency for end users.

---

## 31. Svelte 5 reactivity before external state libraries

Default to `$state`, `$derived`, and `$effect`. A Svelte store or external library is acceptable only when a specific documented need appears.

---

## 32. SSE before WebSockets

Server-to-client events use SSE. User-initiated actions use plain HTTP. WebSockets require an explicit architectural decision.

---

## 33. No infrastructure without evidence

Do not add Redis, PostgreSQL, Celery, Kafka, Docker-only deployment, microservices, or distributed tracing to satisfy a hypothetical future requirement.

---

## 34. Build-time tooling vs runtime architecture

A tool used to build the product is not part of the runtime architecture.

Example: Vite builds the frontend; FastAPI serves the result. The packaged app does not need a separate Node server.

---

## 35. Local resource awareness

The scheduler privileges a stable, responsive machine over maximum concurrency.

CPU, RAM, disk, network, and GPU of the user's computer are the infrastructure limits.

---

## 36. No fake source quality

Never present an upscaled or re-encoded file as equivalent to a native higher-quality source.

`source quality`, `output dimensions`, and `upscaling` are distinct concepts in the UI and in the domain model.
