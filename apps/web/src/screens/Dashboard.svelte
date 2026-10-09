<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import Button from '../lib/components/Button.svelte'
  import Icon from '../lib/icons/Icon.svelte'
  import Skeleton from '../lib/components/Skeleton.svelte'
  import JobCard from '../lib/JobCard.svelte'
  import { live, mergeLive, startLiveUpdates } from '../lib/live'

  interface Props {
    onopen?: (id: string) => void
  }

  const { onopen }: Props = $props()

  let jobs = $state<JobDto[]>([])
  let error = $state<string | null>(null)
  let loaded = $state(false)
  let refreshing = $state(false)

  startLiveUpdates()

  async function refresh(): Promise<void> {
    // Only the first load counts as a skeleton: a background refresh has
    // content to sit behind, and replacing a readable list with a placeholder
    // would be a worse answer than leaving it visible.
    refreshing = true
    try {
      const response = await api.listJobs()
      jobs = response.jobs
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loaded = true
      refreshing = false
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
  <div class="flex items-center justify-between gap-3">
    <div>
      <h1 class="text-lg font-semibold text-ink">Dashboard</h1>
      <p class="mt-1 text-sm text-ink-3">
        <span class="fig">{active.length}</span> active ·
        <span class="fig">{jobs.length}</span> total
      </p>
    </div>
    <Button icon="refresh" busy={refreshing} onclick={() => void refresh()}>Refresh</Button>
  </div>

  {#if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {/if}

  {#if !loaded}
    <Skeleton rows={4} />
  {:else if recent.length === 0}
    <!-- The empty state is the product's front door: someone arrives here from
         the extension holding a URL, so it names that path instead of just
         reporting an absence. -->
    <div
      class="flex flex-col items-center gap-3 rounded-xl border border-dashed border-seam px-6 py-12 text-center"
    >
      <Icon name="download" class="h-6 w-6 text-ink-4" />
      <p class="text-sm text-ink-2">No jobs yet</p>
      <p class="max-w-sm text-xs text-ink-3">
        Paste a URL in <span class="text-ink-2">Resolve</span> to get started, or use the browser extension
        to send the page you are watching straight here.
      </p>
    </div>
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
