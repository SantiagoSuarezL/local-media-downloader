import { derived, get, writable } from 'svelte/store'
import type { JobDto } from '@lmd/contracts'
import { STALE_AFTER_MS, isTerminalState, stageIndex } from './jobState'

export interface LiveJob {
  job_id: string
  state: string | null
  stage: string | null
  percentage: number | null
  downloadedBytes: number | null
  totalBytes: number | null
  speed: number | null
  eta: number | null
  /**
   * When this entry last received a frame. Without it a job that died mid
   * download keeps rendering its last known percentage forever, which reads as
   * progress that is still happening (the original "no se si se quedo
   * congelado" complaint). With it, silence becomes visible as staleness.
   */
  updatedAt: number
}

/** Entries for finished jobs linger briefly so the terminal state paints, then go. */
export const TERMINAL_TTL_MS = 5_000

/**
 * Live progress keyed by job id, fed from the SSE stream. Kept as a module
 * store so the Dashboard and Job details can share one EventSource.
 */
export const live = writable<Record<string, LiveJob>>({})

/**
 * A one-second tick, only running while something is actually in flight.
 *
 * Staleness is a function of elapsed time, so a card cannot decide it is stale
 * from data alone; it needs a clock. Rendering one interval per card would cost
 * more than the thing it reports, so this is a single shared timer that starts
 * with the stream and idles at zero cost when the queue is empty.
 */
export const clock = writable(Date.now())

let source: EventSource | null = null
let ticker: ReturnType<typeof setInterval> | null = null

/** True when at least one job is in flight and the clock needs to tick. */
const hasActiveWork = derived(live, (entries) =>
  Object.values(entries).some((entry) => !isTerminalState(entry.state ?? '')),
)

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
  ticker = setInterval(() => {
    // Only wake subscribers while something is moving.
    if (get(hasActiveWork)) {
      clock.set(Date.now())
    }
    purgeFinished()
  }, 1000)
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
      updatedAt: Date.now(),
    },
  }))
}

/**
 * Drop entries for jobs that finished, so the store cannot grow without bound
 * over a long session and a cleaned-up job cannot keep painting itself.
 */
function purgeFinished(): void {
  const now = Date.now()
  live.update((current) => {
    let changed = false
    const next: Record<string, LiveJob> = {}
    for (const [id, entry] of Object.entries(current)) {
      if (isTerminalState(entry.state ?? '') && now - entry.updatedAt > TERMINAL_TTL_MS) {
        changed = true
        continue
      }
      next[id] = entry
    }
    return changed ? next : current
  })
}

/** Whether a job has gone quiet for longer than its stage tolerates. */
export function isStale(entry: LiveJob, now: number): boolean {
  if (isTerminalState(entry.state ?? '')) {
    return false
  }
  const index = stageIndex(entry.state ?? '', entry.stage)
  if (index === null) {
    return false
  }
  const budget = STALE_AFTER_MS[(['download', 'process', 'validate', 'commit'] as const)[index]]
  return now - entry.updatedAt > budget
}

export function stopLiveUpdates(): void {
  source?.close()
  source = null
  if (ticker !== null) {
    clearInterval(ticker)
    ticker = null
  }
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
