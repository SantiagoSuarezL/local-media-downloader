<script lang="ts">
  import type { CleanupReport, JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { STATE_TONE, formatTimestamp } from '../lib/format'

  interface Props {
    onopen?: (id: string) => void
  }

  const { onopen }: Props = $props()

  const FILTERS = ['ALL', 'ACTIVE', 'COMPLETED', 'FAILED', 'CANCELLED'] as const
  type Filter = (typeof FILTERS)[number]

  const PAGE_SIZE = 50
  const RETRYABLE = ['FAILED', 'CANCELLED', 'RECOVERY_REQUIRED']

  let jobs = $state<JobDto[]>([])
  let nextCursor = $state<string | null>(null)
  let loading = $state(false)
  let filter = $state<Filter>('ALL')
  let error = $state<string | null>(null)
  let query = $state('')
  let retrying = $state<string | null>(null)
  let cleaning = $state(false)
  let cleanupReport = $state<CleanupReport | null>(null)

  function statesFor(value: Filter): string[] | undefined {
    if (value === 'ALL') {
      return undefined
    }
    if (value === 'ACTIVE') {
      return [
        'CREATED',
        'RESOLVING',
        'READY',
        'QUEUED',
        'DOWNLOADING',
        'PROCESSING',
        'VALIDATING',
        'COMMITTING',
        'CANCEL_REQUESTED',
        'RETRY_WAIT',
        'RECOVERY_REQUIRED',
      ]
    }
    return [value]
  }

  async function refresh(): Promise<void> {
    loading = true
    error = null
    try {
      const page = await api.listJobs({ limit: PAGE_SIZE, states: statesFor(filter) })
      jobs = page.jobs
      nextCursor = page.next_cursor
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loading = false
    }
  }

  async function loadMore(): Promise<void> {
    if (!nextCursor || loading) {
      return
    }
    loading = true
    try {
      const page = await api.listJobs({
        limit: PAGE_SIZE,
        cursor: nextCursor,
        states: statesFor(filter),
      })
      jobs = [...jobs, ...page.jobs]
      nextCursor = page.next_cursor
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loading = false
    }
  }

  async function retry(id: string): Promise<void> {
    retrying = id
    try {
      const updated = await api.retryJob(id)
      jobs = jobs.map((job) => (job.id === id ? updated : job))
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      retrying = null
    }
  }

  async function cleanup(): Promise<void> {
    cleaning = true
    try {
      cleanupReport = await api.runCleanup()
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      cleaning = false
    }
  }

  function select(next: Filter): void {
    filter = next
    void refresh()
  }

  void refresh()

  const visible = $derived(
    jobs.filter((job) => {
      const needle = query.trim().toLowerCase()
      return (
        needle === '' ||
        (job.title ?? '').toLowerCase().includes(needle) ||
        (job.source_url ?? '').toLowerCase().includes(needle)
      )
    }),
  )
</script>

<section class="flex flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-lg font-semibold text-neutral-100">History</h1>
    <div class="flex items-center gap-2">
      <input
        type="search"
        class="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100"
        placeholder="Filter by title or URL"
        bind:value={query}
      />
      <button
        type="button"
        class="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50"
        disabled={cleaning}
        onclick={() => void cleanup()}
        title="Apply retention now: redact old URLs, delete old history"
      >
        {cleaning ? 'Cleaning…' : 'Run cleanup'}
      </button>
    </div>
  </div>

  {#if cleanupReport}
    <p
      class="rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2 text-xs text-neutral-400"
    >
      Cleanup: {cleanupReport.urls_redacted} URLs redacted · {cleanupReport.jobs_deleted} jobs deleted
      · {cleanupReport.directories_deleted} directories deleted{#if cleanupReport.errors.length > 0}
        · {cleanupReport.errors.length} errors{/if}
    </p>
  {/if}

  <div class="flex flex-wrap gap-2">
    {#each FILTERS as option (option)}
      <button
        type="button"
        class="rounded-full border px-3 py-1 text-xs {filter === option
          ? 'border-sky-600 bg-sky-950/50 text-sky-200'
          : 'border-neutral-800 text-neutral-400 hover:text-neutral-200'}"
        onclick={() => select(option)}
      >
        {option}
      </button>
    {/each}
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {/if}

  <div class="overflow-x-auto rounded-xl border border-neutral-800">
    <table class="w-full text-left text-xs">
      <thead class="bg-neutral-900/60 text-neutral-500">
        <tr>
          <th class="px-3 py-2">Title</th>
          <th class="px-3 py-2">State</th>
          <th class="px-3 py-2">Priority</th>
          <th class="px-3 py-2">Created</th>
          <th class="px-3 py-2">Attempts</th>
          <th class="px-3 py-2">Error</th>
          <th class="px-3 py-2"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {#each visible as job (job.id)}
          <tr class="border-t border-neutral-800/80 hover:bg-neutral-900/40">
            <td class="px-3 py-2">
              <button
                type="button"
                class="max-w-80 truncate text-left text-neutral-200 hover:text-sky-300"
                onclick={() => onopen?.(job.id)}
              >
                {job.title ?? job.source_url ?? job.id}
              </button>
            </td>
            <td class="px-3 py-2 {STATE_TONE[job.state] ?? 'text-neutral-400'}">{job.state}</td>
            <td class="px-3 py-2 text-neutral-400">{job.priority}</td>
            <td class="px-3 py-2 text-neutral-400">{formatTimestamp(job.created_at)}</td>
            <td class="px-3 py-2 text-neutral-400">{job.attempt_count}</td>
            <td class="px-3 py-2 text-red-400">{job.error_code ?? '—'}</td>
            <td class="px-3 py-2 text-right">
              {#if RETRYABLE.includes(job.state)}
                <button
                  type="button"
                  class="rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-300 hover:border-sky-600 hover:text-sky-300 disabled:opacity-50"
                  disabled={retrying === job.id}
                  onclick={() => void retry(job.id)}
                >
                  {retrying === job.id ? '…' : 'Retry'}
                </button>
              {/if}
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="7" class="px-3 py-6 text-center text-neutral-500">
              {loading ? 'Loading…' : 'No jobs match.'}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if nextCursor}
    <button
      type="button"
      class="mx-auto rounded-lg border border-neutral-800 px-4 py-2 text-sm text-neutral-300 hover:text-neutral-100 disabled:opacity-50"
      disabled={loading}
      onclick={() => void loadMore()}
    >
      {loading ? 'Loading…' : 'Load more'}
    </button>
  {/if}
</section>
