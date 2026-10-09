<script lang="ts">
  import type { CleanupReport, JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { formatRelativeTime, formatTimestamp } from '../lib/format'
  import { isTerminalState } from '../lib/jobState'
  import Button from '../lib/components/Button.svelte'
  import Spinner from '../lib/components/Spinner.svelte'
  import StateBadge from '../lib/components/StateBadge.svelte'
  import { live, mergeLive, startLiveUpdates } from '../lib/live'

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

  startLiveUpdates()

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

  /**
   * Re-read the durable list when a job *state* changes, never on progress
   * ticks. History used to listen to nothing at all, so its table went stale
   * the moment it was rendered while the Dashboard kept moving: two screens
   * disagreeing about the same job. SQLite stays the record (ENGINEERING_PRINCIPLES #10).
   */
  $effect(() => {
    const signature = Object.values($live)
      .map((entry) => `${entry.job_id}:${entry.state}`)
      .sort()
      .join('|')
    if (signature) {
      void refresh()
    }
  })

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

  function isInFlight(job: JobDto): boolean {
    return !isTerminalState(mergeLive(job, $live[job.id]).state)
  }
</script>

<section class="flex flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-lg font-semibold text-ink">History</h1>
    <div class="flex items-center gap-2">
      <input
        type="search"
        class="rounded-lg border border-seam bg-panel px-3 py-1.5 text-sm text-ink placeholder:text-ink-4"
        placeholder="Filter by title or URL"
        bind:value={query}
      />
      <!-- Destructive and irreversible, so it is outlined, never filled, and it
           sits at the end of the row rather than next to the search field. -->
      <Button
        variant="danger"
        icon="cleanup"
        busy={cleaning}
        onclick={() => void cleanup()}
        title="Apply retention now: redact old URLs, delete old history"
      >
        Run cleanup
      </Button>
    </div>
  </div>

  {#if cleanupReport}
    <p class="rounded-lg border border-seam bg-panel px-3 py-2 text-xs text-ink-2">
      Cleanup: {cleanupReport.urls_redacted} URLs redacted · {cleanupReport.jobs_deleted} jobs deleted
      · {cleanupReport.directories_deleted} directories deleted{#if cleanupReport.errors.length > 0}
        · {cleanupReport.errors.length} errors{/if}
    </p>
  {/if}

  <div class="flex flex-wrap gap-2">
    {#each FILTERS as option (option)}
      <button
        type="button"
        class="rounded-full border px-3 py-1 text-xs transition-colors duration-150 {filter ===
        option
          ? 'border-accent-dim bg-accent-wash text-accent-ink'
          : 'border-seam text-ink-3 hover:border-seam-strong hover:text-ink-2'}"
        aria-pressed={filter === option}
        onclick={() => select(option)}
      >
        {option}
      </button>
    {/each}
  </div>

  {#if error}
    <p class="rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit">
      {error}
    </p>
  {/if}

  <div class="overflow-x-auto rounded-xl border border-seam">
    <table class="w-full text-left text-xs">
      <thead class="bg-panel text-ink-3">
        <tr>
          <th class="px-3 py-2 font-medium">Title</th>
          <th class="px-3 py-2 font-medium">State</th>
          <th class="px-3 py-2 font-medium">Priority</th>
          <th class="px-3 py-2 font-medium">Created</th>
          <th class="px-3 py-2 font-medium">Attempts</th>
          <th class="px-3 py-2 font-medium">Error</th>
          <th class="px-3 py-2"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {#each visible as job (job.id)}
          {@const merged = mergeLive(job, $live[job.id])}
          <!--
            The whole row is the target. It already looked clickable (it had a
            hover highlight) while only its title button actually was, which is
            the worst of both: an affordance that lies. role/tabindex make the
            row a legitimate interactive element for assistive tech. The in-flight
            tint is decoration, not state, so it carries no ARIA: `aria-selected`
            is not valid on role=button and the StateBadge column already
            reports the job's state in words.
          -->
          <tr
            class="border-t border-seam/70 transition-colors duration-150
              {isInFlight(job) ? 'bg-accent-wash/30' : 'hover:bg-panel'}
            focus-visible:bg-panel"
            role="button"
            tabindex="0"
            onclick={() => onopen?.(job.id)}
            onkeydown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onopen?.(job.id)
              }
            }}
          >
            <td class="max-w-80 truncate px-3 py-2 text-ink-2">
              {job.title ?? job.source_url ?? job.id}
            </td>
            <td class="px-3 py-2">
              <StateBadge state={merged.state} />
            </td>
            <td class="fig px-3 py-2 text-ink-3">{job.priority}</td>
            <td class="fig px-3 py-2 text-ink-3" title={formatTimestamp(job.created_at)}>
              {formatRelativeTime(job.created_at)}
            </td>
            <td class="fig px-3 py-2 text-ink-3">{job.attempt_count}</td>
            <td class="px-3 py-2 text-crit">{job.error_code ?? '—'}</td>
            <td class="px-3 py-2 text-right">
              {#if RETRYABLE.includes(merged.state)}
                <!-- stopPropagation: the row is also a button now, and a retry
                     click bubbling up would open the job detail on top of it. -->
                <Button
                  variant="ghost"
                  icon="retry"
                  busy={retrying === job.id}
                  onclick={(event) => {
                    event.stopPropagation()
                    void retry(job.id)
                  }}
                >
                  Retry
                </Button>
              {/if}
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="7" class="px-3 py-6 text-center text-ink-3">
              {#if loading}
                <span class="inline-flex items-center gap-2">
                  <Spinner /> Loading history…
                </span>
              {:else}
                No jobs match.
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if nextCursor}
    <Button class="mx-auto" busy={loading} onclick={() => void loadMore()}>Load more</Button>
  {/if}
</section>
