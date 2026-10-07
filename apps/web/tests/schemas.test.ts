import { describe, expect, it } from 'vitest'
import {
  BatchResponseSchema,
  CleanupReportSchema,
  DuplicateJobSchema,
  ErrorEnvelopeSchema,
  HealthDtoSchema,
  JobDtoSchema,
  JobListResponseSchema,
  MediaInfoDtoSchema,
  SettingsDtoSchema,
} from './schemas'

const JOB = {
  id: 'job-1',
  state: 'QUEUED',
  created_at: '2026-10-07T00:00:00.000Z',
  updated_at: '2026-10-07T00:00:00.000Z',
  source_url: 'https://example.com/v',
  title: 'Some video',
  progress: 0,
  current_stage: null,
  error_code: null,
  error_message: null,
  output_path: null,
  priority: 0,
  attempt_count: 0,
}

const FORMAT = {
  id: '22',
  kind: 'combined',
  container: 'mp4',
  extension: 'mp4',
  video_codec: 'avc1.64001F',
  audio_codec: 'mp4a.40.2',
  width: 1280,
  height: 720,
  fps: 30,
  bitrate: null,
  audio_bitrate: 128000,
  filesize: null,
  filesize_approx: true,
  dynamic_range: 'SDR',
  protocol: 'https',
  has_video: true,
  has_audio: true,
  quality_score: 720.5,
  note: null,
}

describe('job contracts', () => {
  it('accepts the exact _job_dict shape', () => {
    expect(JobDtoSchema.safeParse(JOB).success).toBe(true)
  })

  it('rejects a renamed, dropped or extra key', () => {
    const { title, ...withoutTitle } = JOB
    expect(withoutTitle).not.toHaveProperty('title')
    expect(JobDtoSchema.safeParse(withoutTitle).success).toBe(false)
    expect(JobDtoSchema.safeParse({ ...JOB, title }).success).toBe(true)
    expect(JobDtoSchema.safeParse({ ...JOB, extra: 1 }).success).toBe(false)
    expect(JobDtoSchema.safeParse({ ...JOB, id: 42 }).success).toBe(false)
  })

  it('accepts the duplicate envelope and nothing else extra', () => {
    expect(DuplicateJobSchema.safeParse({ ...JOB, duplicate: true }).success).toBe(true)
    expect(DuplicateJobSchema.safeParse(JOB).success).toBe(false)
    expect(DuplicateJobSchema.safeParse({ ...JOB, duplicate: false }).success).toBe(false)
  })

  it('tolerates states the UI does not know yet', () => {
    expect(JobDtoSchema.safeParse({ ...JOB, state: 'SOME_FUTURE_STATE' }).success).toBe(true)
  })

  it('pins the list envelope', () => {
    expect(JobListResponseSchema.safeParse({ jobs: [JOB], next_cursor: 'abc' }).success).toBe(true)
    expect(JobListResponseSchema.safeParse({ jobs: [] }).success).toBe(false)
  })
})

describe('batch contracts', () => {
  it('accepts created, duplicate and error items in order', () => {
    const payload = {
      results: [
        {
          index: 0,
          status: 'created',
          job: { id: 'a', state: 'QUEUED', title: 'V', priority: 0 },
        },
        {
          index: 1,
          status: 'duplicate',
          job: { id: 'b', state: 'DOWNLOADING', title: null, priority: 3 },
        },
        {
          index: 2,
          status: 'error',
          error: { code: 'UNSUPPORTED_PROTOCOL', message: 'nope' },
        },
      ],
    }
    expect(BatchResponseSchema.safeParse(payload).success).toBe(true)
  })

  it('rejects unknown item statuses and malformed errors', () => {
    expect(
      BatchResponseSchema.safeParse({ results: [{ index: 0, status: 'queued' }] }).success,
    ).toBe(false)
    expect(
      BatchResponseSchema.safeParse({
        results: [{ index: 0, status: 'error', error: { code: 42 } }],
      }).success,
    ).toBe(false)
  })
})

describe('error envelope', () => {
  it('accepts the app-level envelope', () => {
    expect(
      ErrorEnvelopeSchema.safeParse({ error: { code: 'NOT_FOUND', message: 'x' } }).success,
    ).toBe(true)
  })

  it('accepts the resolve envelope with the retryable flag', () => {
    const payload = { error: { code: 'NETWORK_ERROR', message: 'x', retryable: true } }
    expect(ErrorEnvelopeSchema.safeParse(payload).success).toBe(true)
  })

  it('rejects HTML-shaped or keyless errors', () => {
    expect(ErrorEnvelopeSchema.safeParse({ message: 'x' }).success).toBe(false)
    expect(ErrorEnvelopeSchema.safeParse({ error: { code: 'X' } }).success).toBe(false)
  })
})

describe('health and settings contracts', () => {
  const HEALTH = {
    status: 'ok',
    version: '0.1.0',
    api: 'ok',
    database: { status: 'ok', detail: 'ok (schema v3)' },
    storage: { status: 'ok', detail: 'writable' },
    tools: {
      yt_dlp: { detected: true, version: '2026.8.19' },
      ffmpeg: { detected: false, version: null },
    },
    extractor: {
      name: 'yt-dlp',
      available: true,
      version: '2026.8.19',
      may_be_outdated: false,
    },
  }

  const SETTINGS = {
    host: '127.0.0.1',
    port: 8765,
    log_level: 'INFO',
    data_dir: 'data',
    database_path: 'data/app.db',
    scheduler_max_active: 3,
    scheduler_max_downloads: 2,
    scheduler_max_encoders: 1,
    scheduler_max_attempts: 3,
    scheduler_retry_backoff_seconds: 2,
    output_root: '/tmp/dl',
    output_rule: 'flat',
    source_url_retention: '7days',
    history_retention_days: 30,
    temporary_retention_hours: 24,
    bandwidth_limit_bps: null,
  }

  it('accepts the exact health and settings shapes', () => {
    expect(HealthDtoSchema.safeParse(HEALTH).success).toBe(true)
    expect(SettingsDtoSchema.safeParse(SETTINGS).success).toBe(true)
  })

  it('rejects tool entries with a renamed key', () => {
    const drifted = {
      ...HEALTH,
      tools: { yt_dlp: { available: true, version: '2026.8.19' } },
    }
    expect(HealthDtoSchema.safeParse(drifted).success).toBe(false)
  })

  it('rejects a degraded status typo', () => {
    expect(HealthDtoSchema.safeParse({ ...HEALTH, status: 'fine' }).success).toBe(false)
  })
})

describe('media info contract', () => {
  const INFO = {
    id: 'dQw4w9WgXcQ',
    source: {
      url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      extractor: 'youtube',
      title: 'Some video',
      uploader: 'Someone',
    },
    duration_seconds: 212,
    thumbnail_url: null,
    is_live: false,
    formats: [FORMAT],
    warnings: [],
  }

  it('accepts the exact MediaInfo shape', () => {
    expect(MediaInfoDtoSchema.safeParse(INFO).success).toBe(true)
  })

  it('never accepts raw extractor internals in a format', () => {
    const leaked = { ...FORMAT, vcodec: 'avc1', tbr: 1000 }
    expect(MediaInfoDtoSchema.safeParse({ ...INFO, formats: [leaked] }).success).toBe(false)
  })
})

describe('cleanup contract', () => {
  it('accepts the retention report shape', () => {
    const report = {
      urls_redacted: 1,
      jobs_deleted: 2,
      directories_deleted: 3,
      errors: ['delete x: boom'],
    }
    expect(CleanupReportSchema.safeParse(report).success).toBe(true)
    expect(CleanupReportSchema.safeParse({ ...report, extra: 0 }).success).toBe(false)
  })
})
