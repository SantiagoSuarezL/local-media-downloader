<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { formatBytes, formatEta, formatTimestamp } from '../lib/format'
  import { clock, isStale, live, mergeLive, startLiveUpdates } from '../lib/live'
  import { isTerminalState, railSummary, railVisible } from '../lib/jobState'
  import Button from '../lib/components/Button.svelte'
  import Icon from '../lib/icons/Icon.svelte'
  import Spinner from '../lib/components/Spinner.svelte'
  import StageRail from '../lib/components/StageRail.svelte'
  import StateBadge from '../lib/components/StateBadge.svelte'

  interface Props {
    jobId: string | null
    oncancelled?: () => void
  }

  const { jobId, oncancelled }: Props = $props()

  let job = $state<JobDto | null>(null)
  let error = $state<string | null>(null)
  let busy = $state(false)
  let priority = $state(0)

  startLiveUpdates()

  async function load(id: string): Promise<void> {
    try {
      job = await api.getJob(id)
      priority = job.priority
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  async function cancel(): Promise<void> {
    if (!job) {
      return
    }
    busy = true
    try {
      job = await api.cancelJob(job.id)
      oncancelled?.()
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      // A cancel that loses the race with completion lands here as a 409
      // while the screen still shows the pre-completion snapshot (the dead
      // "Cancel job" of the ghost). Re-read the durable record first so the
      // screen lands on the truth, then report why the cancel did nothing.
      await load(job.id)
      error = message
    } finally {
      busy = false
    }
  }

  async function retry(): Promise<void> {
    if (!job) {
      return
    }
    busy = true
    try {
      job = await api.retryJob(job.id)
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      busy = false
    }
  }

  async function savePriority(): Promise<void> {
    if (!job || priority === job.priority) {
      return
    }
    busy = true
    try {
      job = await api.setPriority(job.id, priority)
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      busy = false
    }
  }

  // Revalidation guards for the ghost-download snap-back: `load()` reads the
  // durable record once, but the stream keeps moving. After the 5s terminal
  // purge the live entry vanishes and `merged` would fall back to the stale
  // pre-completion snapshot (ghost "downloading" + dead Cancel button).
  let revalidatedFor = $state<string | null>(null)
  let sawLiveFor = $state<string | null>(null)

  $effect(() => {
    if (jobId) {
      revalidatedFor = null
      sawLiveFor = null
      void load(jobId)
    } else {
      job = null
    }
  })

  $effect(() => {
    if (!job || job.id !== jobId) {
      return
    }
    const entry = $live[job.id]
    if (entry && sawLiveFor !== job.id) {
      sawLiveFor = job.id
    }
    const terminal = entry != null && isTerminalState(entry.state ?? '')
    const purgedAfterLive = entry == null && sawLiveFor === job.id && !isTerminalState(job.state)
    if ((terminal || purgedAfterLive) && revalidatedFor !== job.id) {
      revalidatedFor = job.id
      void load(job.id)
    }
  })

  const merged = $derived(job ? mergeLive(job, $live[job.id]) : null)
  const lj = $derived(job ? $live[job.id] : undefined)
  const cancellable = $derived(
    merged !== null && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(merged.state),
  )
  const retryable = $derived(
    merged !== null && ['FAILED', 'CANCELLED', 'RECOVERY_REQUIRED'].includes(merged.state),
  )

  const percent = $derived(Math.round((lj?.percentage ?? (merged?.progress ?? 0) * 100) || 0))
  const stale = $derived(lj ? isStale(lj, $clock) : false)
  const summary = $derived(merged ? railSummary(merged.state, merged.current_stage) : '')

  /**
   * Bytes, speed and ETA exist only while the progress stream is running; the
   * durable record never carries them. Rendering the three rows with permanent
   * em dashes for a finished job read as broken lookups, so they exist only
   * when there is real data to put in them.
   */
  const hasTelemetry = $derived(
    lj != null && (lj.downloadedBytes != null || lj.speed != null || lj.eta != null),
  )
</script>

<section class="flex flex-col gap-6">
  <h1 class="text-lg font-semibold text-ink">Job details</h1>

  {#if !jobId}
    <p class="rounded-xl border border-dashed border-seam p-8 text-center text-sm text-ink-3">
      Pick a job from the dashboard to see its progress, errors and output.
    </p>
  {:else if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {:else if merged}
    <article class="flex flex-col gap-4 rounded-xl border border-seam bg-panel p-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 class="truncate text-base font-semibold text-ink">
            {merged.title ?? merged.id}
          </h2>
          <p class="mt-1 truncate text-xs text-ink-3">{merged.source_url ?? merged.id}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          {#if retryable}
            <Button icon="retry" {busy} onclick={() => void retry()}>Retry job</Button>
          {/if}
          {#if cancellable}
            <Button variant="danger" icon="cancel" {busy} onclick={() => void cancel()}>
              Cancel job
            </Button>
          {/if}
        </div>
      </div>

      <!-- The rail leads here: one job in detail is exactly where "which stage,
           and is it still moving" is the question being asked. Hidden for
           finished jobs, where it would only repeat "Finished" in shape. -->
      <div class="flex flex-col gap-2">
        {#if railVisible(merged.state, merged.current_stage)}
          <StageRail state={merged.state} stage={merged.current_stage} {stale} />
        {/if}
        <div class="flex items-baseline justify-between gap-3">
          <span class="text-xs text-ink-3">
            {stale ? `${summary} · no progress` : summary}
          </span>
          <span class="fig text-xs text-ink-2">{percent}%</span>
        </div>
        <div class="h-1 w-full overflow-hidden rounded-full bg-well">
          <div
            class="h-full rounded-full transition-[width] duration-300 {stale
              ? 'bg-warn'
              : 'bg-accent'}"
            style="width: {Math.min(percent, 100)}%"
          ></div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 text-xs text-ink-3">
        <label for="priority">Priority</label>
        <input
          id="priority"
          type="number"
          class="fig w-20 rounded-lg border border-seam bg-panel px-2 py-1 text-sm text-ink"
          bind:value={priority}
        />
        <Button
          variant="ghost"
          disabled={busy || !job || priority === job.priority}
          onclick={() => void savePriority()}
        >
          Save
        </Button>
        <span class="text-ink-4">Higher preempts lower in the queue.</span>
      </div>

      <dl class="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
        <div>
          <dt class="text-ink-3">State</dt>
          <dd class="mt-0.5"><StateBadge state={merged.state} /></dd>
        </div>
        <div>
          <dt class="text-ink-3">Stage</dt>
          <dd class="mt-0.5 text-ink-2">{merged.current_stage ?? '—'}</dd>
        </div>
        <div>
          <dt class="text-ink-3">Attempts</dt>
          <dd class="fig mt-0.5 text-ink-2">{merged.attempt_count}</dd>
        </div>
        {#if hasTelemetry}
          <div>
            <dt class="text-ink-3">Downloaded</dt>
            <dd class="fig mt-0.5 text-ink-2">
              {formatBytes(lj?.downloadedBytes ?? null)}
              {lj?.totalBytes ? ` / ${formatBytes(lj.totalBytes)}` : ''}
            </dd>
          </div>
          <div>
            <dt class="text-ink-3">Speed</dt>
            <dd class="fig mt-0.5 text-ink-2">{formatBytes(lj?.speed ?? null)}/s</dd>
          </div>
          <div>
            <dt class="text-ink-3">ETA</dt>
            <dd class="fig mt-0.5 text-ink-2">{formatEta(lj?.eta ?? null)}</dd>
          </div>
        {/if}
        <div class="col-span-2 sm:col-span-3">
          <dt class="text-ink-3">Output</dt>
          <dd class="mt-0.5 flex items-start gap-1.5 break-all text-ink-2">
            {#if merged.output_path}
              <Icon name="folder" class="mt-px h-3.5 w-3.5 shrink-0 text-ink-4" />
              {merged.output_path}
            {:else}
              —
            {/if}
          </dd>
        </div>
      </dl>

      {#if merged.error_code}
        <div class="rounded-lg border border-crit/40 bg-crit/10 px-3 py-2">
          <p class="text-sm font-medium text-crit">{merged.error_code}</p>
          <p class="mt-1 text-xs text-crit/80">{merged.error_message}</p>
        </div>
      {/if}

      <p class="fig text-xs text-ink-4">
        Job id {merged.id} · created {formatTimestamp(merged.created_at)}
      </p>
    </article>
  {:else}
    <div class="flex items-center gap-2 text-sm text-ink-3" role="status" aria-busy="true">
      <Spinner /> Loading job…
    </div>
  {/if}
</section>
