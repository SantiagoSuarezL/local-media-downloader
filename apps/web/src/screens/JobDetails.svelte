<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { formatBytes, formatEta, formatTimestamp } from '../lib/format'
  import { live, mergeLive, startLiveUpdates } from '../lib/live'

  interface Props {
    jobId: string | null
    oncancelled?: () => void
  }

  const { jobId, oncancelled }: Props = $props()

  let job = $state<JobDto | null>(null)
  let error = $state<string | null>(null)

  startLiveUpdates()

  async function load(id: string): Promise<void> {
    try {
      job = await api.getJob(id)
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  async function cancel(): Promise<void> {
    if (!job) {
      return
    }
    try {
      job = await api.cancelJob(job.id)
      oncancelled?.()
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  $effect(() => {
    if (jobId) {
      void load(jobId)
    } else {
      job = null
    }
  })

  const merged = $derived(job ? mergeLive(job, $live[job.id]) : null)
  const lj = $derived(job ? $live[job.id] : undefined)
  const cancellable = $derived(
    merged !== null && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(merged.state),
  )
</script>

<section class="flex flex-col gap-6">
  <h1 class="text-lg font-semibold text-neutral-100">Job details</h1>

  {#if !jobId}
    <p
      class="rounded-xl border border-dashed border-neutral-800 p-8 text-center text-sm text-neutral-500"
    >
      Pick a job from the dashboard to see its progress, errors and output.
    </p>
  {:else if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {:else if merged}
    <article class="flex flex-col gap-4 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="truncate text-base font-semibold text-neutral-100">
            {merged.title ?? merged.id}
          </h2>
          <p class="mt-1 truncate text-xs text-neutral-500">{merged.source_url ?? merged.id}</p>
        </div>
        {#if cancellable}
          <button
            type="button"
            class="shrink-0 rounded-lg border border-red-900 px-3 py-1.5 text-sm text-red-300 hover:bg-red-950/40"
            onclick={() => void cancel()}
          >
            Cancel job
          </button>
        {/if}
      </div>

      <dl class="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
        <div>
          <dt class="text-neutral-500">State</dt>
          <dd class="mt-0.5 text-neutral-200">{merged.state}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Stage</dt>
          <dd class="mt-0.5 text-neutral-200">{merged.current_stage ?? '—'}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Attempts</dt>
          <dd class="mt-0.5 text-neutral-200">{merged.attempt_count}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Downloaded</dt>
          <dd class="mt-0.5 text-neutral-200">
            {formatBytes(lj?.downloadedBytes ?? null)}
            {lj?.totalBytes ? ` / ${formatBytes(lj.totalBytes)}` : ''}
          </dd>
        </div>
        <div>
          <dt class="text-neutral-500">Speed</dt>
          <dd class="mt-0.5 text-neutral-200">{formatBytes(lj?.speed ?? null)}/s</dd>
        </div>
        <div>
          <dt class="text-neutral-500">ETA</dt>
          <dd class="mt-0.5 text-neutral-200">{formatEta(lj?.eta ?? null)}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Output</dt>
          <dd class="mt-0.5 break-all text-neutral-200">{merged.output_path ?? '—'}</dd>
        </div>
      </dl>

      {#if merged.error_code}
        <div class="rounded-lg border border-red-900 bg-red-950/30 px-3 py-2">
          <p class="text-sm font-medium text-red-300">{merged.error_code}</p>
          <p class="mt-1 text-xs text-red-200/80">{merged.error_message}</p>
        </div>
      {/if}

      <p class="text-xs text-neutral-600">
        Job id {merged.id} · created {formatTimestamp(merged.created_at)}
      </p>
    </article>
  {:else}
    <p class="text-sm text-neutral-500">Loading…</p>
  {/if}
</section>
