<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { STATE_TONE, formatTimestamp } from '../lib/format'

  interface Props {
    onopen?: (id: string) => void
  }

  const { onopen }: Props = $props()

  const FILTERS = ['ALL', 'ACTIVE', 'COMPLETED', 'FAILED', 'CANCELLED'] as const
  type Filter = (typeof FILTERS)[number]

  let jobs = $state<JobDto[]>([])
  let filter = $state<Filter>('ALL')
  let error = $state<string | null>(null)
  let query = $state('')

  async function refresh(): Promise<void> {
    try {
      jobs = (await api.listJobs()).jobs
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  void refresh()

  const visible = $derived(
    jobs.filter((job) => {
      const matchesFilter =
        filter === 'ALL' ||
        (filter === 'ACTIVE'
          ? !['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.state)
          : job.state === filter)
      const needle = query.trim().toLowerCase()
      const matchesQuery =
        needle === '' ||
        (job.title ?? '').toLowerCase().includes(needle) ||
        (job.source_url ?? '').toLowerCase().includes(needle)
      return matchesFilter && matchesQuery
    }),
  )
</script>

<section class="flex flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-lg font-semibold text-neutral-100">History</h1>
    <input
      type="search"
      class="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100"
      placeholder="Filter by title or URL"
      bind:value={query}
    />
  </div>

  <div class="flex flex-wrap gap-2">
    {#each FILTERS as option (option)}
      <button
        type="button"
        class="rounded-full border px-3 py-1 text-xs {filter === option
          ? 'border-sky-600 bg-sky-950/50 text-sky-200'
          : 'border-neutral-800 text-neutral-400 hover:text-neutral-200'}"
        onclick={() => (filter = option)}
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
          <th class="px-3 py-2">Created</th>
          <th class="px-3 py-2">Attempts</th>
          <th class="px-3 py-2">Error</th>
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
            <td class="px-3 py-2 text-neutral-400">{formatTimestamp(job.created_at)}</td>
            <td class="px-3 py-2 text-neutral-400">{job.attempt_count}</td>
            <td class="px-3 py-2 text-red-400">{job.error_code ?? '—'}</td>
          </tr>
        {:else}
          <tr>
            <td colspan="5" class="px-3 py-6 text-center text-neutral-500">No jobs match.</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>
