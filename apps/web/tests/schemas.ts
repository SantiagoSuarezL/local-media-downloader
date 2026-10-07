import { z } from 'zod'

/**
 * Frontend half of the API contract (test-only: `zod` is a devDependency, so
 * these schemas never ship to the dashboard bundle).
 *
 * Every schema is `.strict()`: a backend change that renames, drops or adds
 * a top-level key fails here instead of breaking the UI at runtime. The
 * backend half lives in `apps/api/tests/test_contracts.py`, which asserts the
 * same key sets from the real FastAPI responses — the two suites must be
 * updated together when a DTO changes on purpose.
 *
 * `state` fields stay `z.string()` on purpose: the UI must tolerate states it
 * does not know yet. The contract pins key sets, not value sets.
 */

export const ErrorEnvelopeSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string(),
        retryable: z.boolean().optional(),
      })
      .strict(),
  })
  .strict()

export const JobDtoSchema = z
  .object({
    id: z.string(),
    state: z.string(),
    created_at: z.string(),
    updated_at: z.string(),
    source_url: z.string().nullable(),
    title: z.string().nullable(),
    progress: z.number(),
    current_stage: z.string().nullable(),
    error_code: z.string().nullable(),
    error_message: z.string().nullable(),
    output_path: z.string().nullable(),
    priority: z.number(),
    attempt_count: z.number(),
  })
  .strict()

export const DuplicateJobSchema = JobDtoSchema.extend({ duplicate: z.literal(true) })

export const JobListResponseSchema = z
  .object({
    jobs: z.array(JobDtoSchema),
    next_cursor: z.string().nullable(),
  })
  .strict()

export const BatchItemResultSchema = z
  .object({
    index: z.number(),
    status: z.enum(['created', 'duplicate', 'error']),
    job: z
      .object({
        id: z.string(),
        state: z.string(),
        title: z.string().nullable(),
        priority: z.number(),
      })
      .strict()
      .optional(),
    error: z.object({ code: z.string(), message: z.string().nullable() }).strict().optional(),
  })
  .strict()

export const BatchResponseSchema = z.object({ results: z.array(BatchItemResultSchema) }).strict()

export const CleanupReportSchema = z
  .object({
    urls_redacted: z.number(),
    jobs_deleted: z.number(),
    directories_deleted: z.number(),
    errors: z.array(z.string()),
  })
  .strict()

export const HealthDtoSchema = z
  .object({
    status: z.enum(['ok', 'degraded']),
    version: z.string(),
    api: z.string(),
    database: z.object({ status: z.string(), detail: z.string() }).strict(),
    storage: z.object({ status: z.string(), detail: z.string() }).strict(),
    tools: z.record(z.object({ detected: z.boolean(), version: z.string().nullable() }).strict()),
    extractor: z
      .object({
        name: z.string(),
        available: z.boolean(),
        version: z.string().nullable(),
        may_be_outdated: z.boolean().nullable(),
      })
      .strict(),
  })
  .strict()

export const SettingsDtoSchema = z
  .object({
    host: z.string(),
    port: z.number(),
    log_level: z.string(),
    data_dir: z.string(),
    database_path: z.string(),
    scheduler_max_active: z.number(),
    scheduler_max_downloads: z.number(),
    scheduler_max_encoders: z.number(),
    scheduler_max_attempts: z.number(),
    scheduler_retry_backoff_seconds: z.number(),
    output_root: z.string(),
    output_rule: z.string(),
    source_url_retention: z.string(),
    history_retention_days: z.number(),
    temporary_retention_hours: z.number(),
    bandwidth_limit_bps: z.number().nullable(),
  })
  .strict()

export const MediaFormatDtoSchema = z
  .object({
    id: z.string(),
    kind: z.enum(['video', 'audio', 'combined']),
    container: z.string().nullable(),
    extension: z.string().nullable(),
    video_codec: z.string().nullable(),
    audio_codec: z.string().nullable(),
    width: z.number().nullable(),
    height: z.number().nullable(),
    fps: z.number().nullable(),
    bitrate: z.number().nullable(),
    audio_bitrate: z.number().nullable(),
    filesize: z.number().nullable(),
    filesize_approx: z.boolean(),
    dynamic_range: z.string().nullable(),
    protocol: z.string().nullable(),
    has_video: z.boolean(),
    has_audio: z.boolean(),
    quality_score: z.number(),
    note: z.string().nullable(),
  })
  .strict()

export const MediaInfoDtoSchema = z
  .object({
    id: z.string(),
    source: z
      .object({
        url: z.string().nullable(),
        extractor: z.string().nullable(),
        title: z.string().nullable(),
        uploader: z.string().nullable(),
      })
      .strict(),
    duration_seconds: z.number().nullable(),
    thumbnail_url: z.string().nullable(),
    is_live: z.boolean(),
    formats: z.array(MediaFormatDtoSchema),
    warnings: z.array(z.string()),
  })
  .strict()
