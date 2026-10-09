import { describe, expect, it } from 'vitest'
import {
  STAGES,
  isTerminalState,
  railFor,
  railSummary,
  railVisible,
  stageIndex,
  toneFor,
} from '../src/lib/jobState'

describe('stageIndex', () => {
  it('finds the segment from the state name', () => {
    expect(stageIndex('DOWNLOADING')).toBe(0)
    expect(stageIndex('PROCESSING')).toBe(1)
    expect(stageIndex('VALIDATING')).toBe(2)
    expect(stageIndex('COMMITTING')).toBe(3)
  })

  it('prefers the explicit stage when the state does not name one', () => {
    expect(stageIndex('RECOVERY_REQUIRED', 'process')).toBe(1)
    expect(stageIndex('FAILED', 'validate')).toBe(2)
  })

  it('returns null for states outside the pipeline', () => {
    expect(stageIndex('QUEUED')).toBeNull()
    expect(stageIndex('CANCEL_REQUESTED')).toBeNull()
  })
})

describe('railFor', () => {
  it('lights exactly one segment while running', () => {
    expect(railFor('PROCESSING')).toEqual(['done', 'active', 'todo', 'todo'])
  })

  it('fills every segment on completion', () => {
    expect(railFor('COMPLETED')).toEqual(['done', 'done', 'done', 'done'])
  })

  it('marks the stopping segment as failed rather than active', () => {
    expect(railFor('FAILED', 'process')).toEqual(['done', 'failed', 'todo', 'todo'])
  })

  it('distinguishes a halt from a failure', () => {
    expect(railFor('CANCELLED', 'process')).toEqual(['done', 'halted', 'todo', 'todo'])
    expect(railFor('RECOVERY_REQUIRED', 'process')).toEqual(['done', 'halted', 'todo', 'todo'])
  })

  it('never implies work for a job that has not started', () => {
    // The load-bearing case: a queued job must not look like it is in a stage.
    expect(railFor('QUEUED')).toEqual(['todo', 'todo', 'todo', 'todo'])
    expect(railFor('CANCEL_REQUESTED')).toEqual(['todo', 'todo', 'todo', 'todo'])
  })
})

describe('railVisible', () => {
  it('renders while a stage is in play, whatever the outcome', () => {
    expect(railVisible('DOWNLOADING')).toBe(true)
    expect(railVisible('PROCESSING')).toBe(true)
    // A job that died inside the pipeline still has a story to tell: the
    // segment it stopped on lights crit/warn and that is the whole point.
    expect(railVisible('FAILED', 'process')).toBe(true)
    expect(railVisible('CANCELLED', 'process')).toBe(true)
    expect(railVisible('RECOVERY_REQUIRED', 'download')).toBe(true)
  })

  it('never renders for a finished job', () => {
    // The user-reported ghost bar: four dim segments under the title of a
    // completed download read as a second, broken loading bar. "Finished",
    // the green badge and 100% already say everything it could say.
    expect(railVisible('COMPLETED')).toBe(false)
    expect(railVisible('COMPLETED', 'commit')).toBe(false)
  })

  it('never renders outside the pipeline', () => {
    expect(railVisible('QUEUED')).toBe(false)
    expect(railVisible('RETRY_WAIT')).toBe(false)
    expect(railVisible('CANCEL_REQUESTED')).toBe(false)
    // Failed before the pipeline started: there is no segment to point at,
    // so the summary word carries the whole story alone.
    expect(railVisible('FAILED')).toBe(false)
    expect(railVisible('CANCELLED')).toBe(false)
  })
})

describe('railSummary', () => {
  it('names the stage in words, never colour alone', () => {
    expect(railSummary('DOWNLOADING')).toBe('Download')
    expect(railSummary('QUEUED')).toBe('Waiting for a worker')
    expect(railSummary('COMPLETED')).toBe('Finished')
    expect(railSummary('FAILED', 'process')).toBe('Failed')
    expect(railSummary('CANCELLED')).toBe('Cancelled')
  })
})

describe('toneFor', () => {
  it('separates running from waiting from dead', () => {
    expect(toneFor('DOWNLOADING')).toBe('accent')
    expect(toneFor('QUEUED')).toBe('idle')
    expect(toneFor('COMPLETED')).toBe('ok')
    expect(toneFor('FAILED')).toBe('crit')
    expect(toneFor('RETRY_WAIT')).toBe('warn')
  })

  it('falls back to idle for an unknown state instead of throwing', () => {
    expect(toneFor('SOMETHING_NEW')).toBe('idle')
  })
})

describe('isTerminalState', () => {
  it('marks only the three terminal states', () => {
    expect(isTerminalState('COMPLETED')).toBe(true)
    expect(isTerminalState('FAILED')).toBe(true)
    expect(isTerminalState('CANCELLED')).toBe(true)
    expect(isTerminalState('DOWNLOADING')).toBe(false)
  })
})

describe('STAGES', () => {
  it('has exactly the four pipeline stages the rail renders', () => {
    expect(STAGES).toHaveLength(4)
    expect(STAGES.map((s) => s.key)).toEqual(['download', 'process', 'validate', 'commit'])
  })
})
