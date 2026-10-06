import { writable } from 'svelte/store'
import type { JobDto } from '@lmd/contracts'

export interface LiveJob {
  job_id: string
  state: string | null
  stage: string | null
  percentage: number | null
  downloadedBytes: number | null
  totalBytes: number | null
  speed: number | null
  eta: number | null
}

/**
 * Live progress keyed by job id, fed from the SSE stream. Kept as a module
 * store so the Dashboard and Job details can share one EventSource.
 */
export const live = writable<Record<string, LiveJob>>({})

let source: EventSource | null = null

export function startLiveUpdates(): void {
  if (source) {
    return
  }
  source = new EventSource('/api/v1/events')
  for (const kind of ['progress', 'state', 'scheduler']) {
    source.addEventListener(kind, (message) => {
      try {
        ingest(JSON.parse((message as MessageEvent).data as string) as Record<string, unknown>)
      } catch {
        // keep the raw stream best-effort
      }
    })
  }
}

function ingest(payload: Record<string, unknown>): void {
  const jobId = payload.job_id
  if (typeof jobId !== 'string') {
    return
  }
  live.update((current) => ({
    ...current,
    [jobId]: {
      job_id: jobId,
      state: typeof payload.state === 'string' ? payload.state : (current[jobId]?.state ?? null),
      stage: typeof payload.stage === 'string' ? payload.stage : (current[jobId]?.stage ?? null),
      percentage:
        typeof payload.percentage === 'number'
          ? payload.percentage
          : (current[jobId]?.percentage ?? null),
      downloadedBytes:
        typeof payload.downloaded_bytes === 'number'
          ? payload.downloaded_bytes
          : (current[jobId]?.downloadedBytes ?? null),
      totalBytes:
        typeof payload.total_bytes === 'number'
          ? payload.total_bytes
          : (current[jobId]?.totalBytes ?? null),
      speed:
        typeof payload.speed_bytes_per_second === 'number'
          ? payload.speed_bytes_per_second
          : (current[jobId]?.speed ?? null),
      eta:
        typeof payload.eta_seconds === 'number'
          ? payload.eta_seconds
          : (current[jobId]?.eta ?? null),
    },
  }))
}

export function stopLiveUpdates(): void {
  source?.close()
  source = null
}

export function mergeLive(job: JobDto, liveJob: LiveJob | undefined): JobDto {
  if (!liveJob) {
    return job
  }
  return {
    ...job,
    state: (liveJob.state as JobDto['state']) ?? job.state,
    progress:
      liveJob.percentage != null
        ? Math.min(Math.max(liveJob.percentage / 100, 0), 1)
        : job.progress,
    current_stage: liveJob.stage ?? job.current_stage,
  }
}
