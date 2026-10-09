/**
 * Job state as the UI needs to read it: which pipeline segment is lit, what
 * tone the lamp takes, and how long silence means "stuck".
 *
 * This replaces `STATE_TONE`'s old job of painting state words in colour.
 * Colour alone cannot say whether a job is working, waiting or dead, so every
 * state now carries a lamp tone AND a segment position AND a staleness budget.
 */

/**
 * `match` is the stem a state name is built from, which is not always the full
 * stage key: the state is `VALIDATING`, not `VALIDATE`, so a plain
 * `includes(key)` never matches it and the rail would show a running validation
 * as having no stage at all.
 */
export const STAGES = [
  { key: 'download', label: 'Download', match: 'download' },
  { key: 'process', label: 'Process', match: 'process' },
  { key: 'validate', label: 'Validate', match: 'validat' },
  { key: 'commit', label: 'Commit', match: 'commit' },
] as const

export type StageKey = (typeof STAGES)[number]['key']

/** Status of one segment of the stage rail. */
export type SegmentStatus = 'done' | 'active' | 'todo' | 'failed' | 'halted'

export type Tone = 'ok' | 'warn' | 'crit' | 'accent' | 'idle'

/**
 * How long a stage may report nothing before the UI says so.
 *
 * The download stage emits a progress frame constantly, so a short budget is
 * safe there. FFmpeg is the opposite: it can run for a long stretch emitting
 * nothing at all, so a short budget would cry wolf on every long transcode.
 * A budget that cries wolf is worse than no budget, because it trains the
 * visitor to ignore the warning that matters.
 */
export const STALE_AFTER_MS: Record<StageKey, number> = {
  download: 15_000,
  process: 90_000,
  validate: 45_000,
  commit: 20_000,
}

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED'])

export function isTerminalState(state: string): boolean {
  return TERMINAL.has(state)
}

const TONES: Record<string, Tone> = {
  COMPLETED: 'ok',
  FAILED: 'crit',
  CANCELLED: 'idle',
  RECOVERY_REQUIRED: 'warn',
  RETRY_WAIT: 'warn',
  CANCEL_REQUESTED: 'warn',
  DOWNLOADING: 'accent',
  PROCESSING: 'accent',
  VALIDATING: 'accent',
  COMMITTING: 'accent',
}

export function toneFor(state: string): Tone {
  return TONES[state] ?? 'idle'
}

/** Index of the segment a state belongs to, or null when it sits outside the pipeline. */
export function stageIndex(state: string, stage?: string | null): number | null {
  if (stage) {
    const byStage = STAGES.findIndex((s) => s.key === stage.toLowerCase())
    if (byStage !== -1) {
      return byStage
    }
  }
  const lowered = state.toLowerCase()
  const byState = STAGES.findIndex((s) => lowered.includes(s.match))
  return byState === -1 ? null : byState
}

/**
 * The four segments for a job. A job outside the pipeline (queued, retrying,
 * cancelled before it started) returns all-todo rather than guessing, so the
 * rail never implies work that is not happening.
 */
export function railFor(state: string, stage?: string | null): SegmentStatus[] {
  if (state === 'COMPLETED') {
    return STAGES.map(() => 'done')
  }

  const index = stageIndex(state, stage)
  if (index === null) {
    return STAGES.map(() => 'todo')
  }

  const failed = state === 'FAILED'
  const halted = state === 'CANCELLED' || state === 'RECOVERY_REQUIRED'

  return STAGES.map((_, i) => {
    if (i < index) {
      return 'done'
    }
    if (i > index) {
      return 'todo'
    }
    return failed ? 'failed' : halted ? 'halted' : 'active'
  })
}

/**
 * Whether the stage rail should render at all. The rail answers "which stage,
 * and is it still moving?" -- a question that only exists while a job is
 * inside the pipeline or stopped inside it. For a finished job the four dim
 * segments say nothing the summary line and the badge do not already say, and
 * under the title they read as a second, broken loading bar.
 */
export function railVisible(state: string, stage?: string | null): boolean {
  if (state === 'COMPLETED') {
    return false
  }
  return stageIndex(state, stage) !== null
}

/** The human sentence under the rail, so the rail is never the only signal. */
export function railSummary(state: string, stage?: string | null): string {
  if (state === 'COMPLETED') {
    return 'Finished'
  }
  if (state === 'FAILED') {
    return 'Failed'
  }
  if (state === 'CANCELLED') {
    return 'Cancelled'
  }
  if (state === 'RECOVERY_REQUIRED') {
    return 'Needs recovery'
  }
  if (state === 'RETRY_WAIT') {
    return 'Waiting to retry'
  }
  if (state === 'CANCEL_REQUESTED') {
    return 'Stopping'
  }
  if (state === 'QUEUED') {
    return 'Waiting for a worker'
  }
  const index = stageIndex(state, stage)
  if (index === null) {
    return 'Preparing'
  }
  return STAGES[index].label
}
