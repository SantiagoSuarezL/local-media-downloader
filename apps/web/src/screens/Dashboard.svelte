<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import JobCard from '../lib/JobCard.svelte'
  import { live, mergeLive, startLiveUpdates } from '../lib/live'

  interface Props {
    onopen?: (id: string) => void
  }

  const { onopen }: Props = $props()

  let jobs = $state<JobDto[]>([])
  let error = $state<string | null>(null)

  startLiveUpdates()

  async function refresh(): Promise<void> {
    try {
      const response = await api.listJobs()
      jobs = response.jobs
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  async function cancel(id: string): Promise<void> {
    try {
      await api.cancelJob(id)
      await refresh()
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  $effect(() => {
    // The stream is only a trigger, never the record: re-read the durable list
    // when a job *state* changes (progress ticks would refetch too often).
    // SQLite stays the source of truth (ENGINEERING_PRINCIPLES #10).
    const signature = Object.values($live)
      .map((job) => `${job.job_id}:${job.state}`)
      .sort()
      .join('|')
    if (signature) {
      void refresh()
    }
  })

  void refresh()

  const active = $derived(
    jobs.filter((job) => !['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.state)),
  )
  const recent = $derived(jobs.slice(0, 12))
</script>

<section class="flex flex-col gap-6">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-lg font-semibold text-neutral-100">Dashboard</h1>
      <p class="mt-1 text-sm text-neutral-500">
        {active.length} active · {jobs.length} total
      </p>
    </div>
    <button
      type="button"
      class="rounded-lg border border-neutral-800 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-900"
      onclick={() => void refresh()}
    >
      Refresh
    </button>
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {/if}

  {#if recent.length === 0}
    <p
      class="rounded-xl border border-dashed border-neutral-800 p-8 text-center text-sm text-neutral-500"
    >
      No jobs yet. Paste a URL in Resolve to get started.
    </p>
  {:else}
    <ul class="flex flex-col gap-3">
      {#each recent as job (job.id)}
        {@const merged = mergeLive(job, $live[job.id])}
        <JobCard
          job={merged}
          live={$live[job.id]}
          onopen={(id) => onopen?.(id)}
          oncancel={(id) => void cancel(id)}
        />
      {/each}
    </ul>
  {/if}
</section>
