/**
 * Shared API contract types consumed by `@lmd/web` and `@lmd/extension`.
 *
 * The concrete schemas mirror the FastAPI responses in `apps/api`. Nothing
 * here may encode media extraction rules or yt-dlp/FFmpeg syntax.
 */

export type JobState =
  | 'CREATED'
  | 'RESOLVING'
  | 'READY'
  | 'QUEUED'
  | 'DOWNLOADING'
  | 'PROCESSING'
  | 'VALIDATING'
  | 'COMMITTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCEL_REQUESTED'
  | 'CANCELLED'
  | 'RETRY_WAIT'
  | 'RECOVERY_REQUIRED'

export interface JobDto {
  id: string
  state: JobState
  created_at: string
  updated_at: string
  source_url: string | null
  title: string | null
  progress: number
  current_stage: string | null
  error_code: string | null
  error_message: string | null
  output_path: string | null
  priority: number
  attempt_count: number
}

export interface JobListResponse {
  jobs: JobDto[]
}

export interface MediaSourceDto {
  url: string | null
  extractor: string | null
  title: string | null
  uploader: string | null
}

export interface MediaFormatDto {
  id: string
  kind: 'video' | 'audio' | 'combined'
  container: string | null
  extension: string | null
  video_codec: string | null
  audio_codec: string | null
  width: number | null
  height: number | null
  fps: number | null
  bitrate: number | null
  audio_bitrate: number | null
  filesize: number | null
  filesize_approx: boolean
  dynamic_range: string | null
  protocol: string | null
  has_video: boolean
  has_audio: boolean
  quality_score: number
  note: string | null
}

export interface MediaInfoDto {
  source: MediaSourceDto
  id: string
  duration_seconds: number | null
  thumbnail_url: string | null
  is_live: boolean
  formats: MediaFormatDto[]
  warnings: string[]
}

export interface OutputIntent {
  media: 'video' | 'audio'
  quality: 'best' | 'worst'
  container: string
  audio: 'include' | 'remove' | 'only'
  video_codec: string
  processing: { resize: string | null; trim: string | null }
}

export interface CreateJobRequest {
  url: string
  intent: OutputIntent
  title?: string
  priority?: number
}

export interface ToolStatusDto {
  detected: boolean
  version: string | null
}

export interface HealthDto {
  status: 'ok' | 'degraded'
  version: string
  api: string
  database: { status: string; detail: string }
  storage: { status: string; detail: string }
  tools: Record<string, ToolStatusDto>
  extractor: {
    name: string
    available: boolean
    version: string | null
    may_be_outdated: boolean | null
  }
}

export interface SettingsDto {
  host: string
  port: number
  log_level: string
  data_dir: string
  database_path: string
  scheduler_max_active: number
  scheduler_max_downloads: number
  scheduler_max_encoders: number
  scheduler_max_attempts: number
  scheduler_retry_backoff_seconds: number
}

export interface JobEventPayload {
  job_id?: string
  state?: JobState
  stage?: string
  percentage?: number
  downloaded_bytes?: number
  total_bytes?: number | null
  speed_bytes_per_second?: number | null
  eta_seconds?: number | null
  error_code?: string
  event?: string
  reason?: string
}
