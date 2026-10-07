// @vitest-environment jsdom
import type { JobDto } from '@lmd/contracts'
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'
import JobCard from '../src/lib/JobCard.svelte'

afterEach(() => {
  cleanup()
})

function makeJob(overrides: Partial<JobDto> = {}): JobDto {
  return {
    id: 'job-1',
    state: 'QUEUED',
    created_at: '2026-10-07T00:00:00Z',
    updated_at: '2026-10-07T00:00:00Z',
    source_url: 'https://example.com/v',
    title: 'Some video',
    progress: 0,
    current_stage: null,
    error_code: null,
    error_message: null,
    output_path: null,
    priority: 0,
    attempt_count: 0,
    ...overrides,
  }
}

describe('JobCard', () => {
  it('renders the title and the state', () => {
    render(JobCard, { props: { job: makeJob() } })
    expect(screen.getByText('Some video')).toBeTruthy()
    expect(screen.getByText('QUEUED')).toBeTruthy()
  })

  it('falls back to the url and then the id when there is no title', () => {
    render(JobCard, {
      props: { job: makeJob({ title: null, source_url: null, id: 'abc' }) },
    })
    // Both the headline and the subtitle fall back to the id.
    expect(screen.getAllByText('abc')).toHaveLength(2)
  })

  it('shows Cancel on an in-flight job and reports its id', async () => {
    const oncancel = vi.fn()
    render(JobCard, { props: { job: makeJob({ state: 'QUEUED' }), oncancel } })
    await fireEvent.click(screen.getByText('Cancel'))
    expect(oncancel).toHaveBeenCalledWith('job-1')
  })

  it('shows Cancel on every non-terminal state, including QUEUED', () => {
    for (const state of [
      'QUEUED',
      'DOWNLOADING',
      'PROCESSING',
      'RETRY_WAIT',
      'CANCEL_REQUESTED',
    ] as const) {
      cleanup()
      render(JobCard, { props: { job: makeJob({ state }) } })
      expect(screen.queryByText('Cancel')).toBeTruthy()
    }
  })

  it('hides Cancel on terminal states', () => {
    for (const state of ['COMPLETED', 'FAILED', 'CANCELLED'] as const) {
      cleanup()
      render(JobCard, { props: { job: makeJob({ state }) } })
      expect(screen.queryByText('Cancel')).toBeNull()
    }
  })

  it('hides Cancel when the parent disables cancellation', () => {
    render(JobCard, { props: { job: makeJob({ state: 'QUEUED' }), cancellable: false } })
    expect(screen.queryByText('Cancel')).toBeNull()
  })

  it('shows the backend error on failed jobs', () => {
    render(JobCard, {
      props: { job: makeJob({ state: 'FAILED', error_code: 'NET', error_message: 'boom' }) },
    })
    expect(screen.getByText('NET: boom')).toBeTruthy()
  })

  it('prefers live progress over the stored snapshot', () => {
    render(JobCard, {
      props: {
        job: makeJob({ progress: 0.1 }),
        live: {
          job_id: 'job-1',
          state: 'DOWNLOADING',
          stage: 'download',
          percentage: 50,
          downloadedBytes: null,
          totalBytes: null,
          speed: null,
          eta: null,
        },
      },
    })
    expect(screen.getByText('50%')).toBeTruthy()
    expect(screen.getByText('DOWNLOADING')).toBeTruthy()
  })
})
