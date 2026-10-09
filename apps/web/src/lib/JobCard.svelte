<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { formatBytes, formatEta } from '../lib/format'
  import { railSummary, railVisible } from '../lib/jobState'
  import { clock, isStale, type LiveJob } from '../lib/live'
  import Button from './components/Button.svelte'
  import StageRail from './components/StageRail.svelte'
  import StateBadge from './components/StateBadge.svelte'

  interface Props {
    job: JobDto
    live?: LiveJob | undefined
    onopen?: (id: string) => void
    oncancel?: (id: string) => void
    cancellable?: boolean
  }

  const { job, live, onopen, oncancel, cancellable = true }: Props = $props()

  const percent = $derived(Math.round((live?.percentage ?? job.progress * 100) || 0))
  const state = $derived(live?.state ?? job.state)
  const stage = $derived(live?.stage ?? job.current_stage)
  const canCancel = $derived(cancellable && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(state))

  /**
   * Silence past the stage's budget. This is the honest answer to "is it
   * stuck?": the rail stops pulsing, the figures stop counting, and the card
   * says so in words. No spinner is involved, because nothing is in flight.
   */
  const stale = $derived(live ? isStale(live, $clock) : false)
  const summary = $derived(railSummary(state, stage))
</script>

<li
  class="group flex flex-col gap-3 rounded-xl border border-seam bg-panel p-4 transition-colors duration-200 hover:border-seam-strong"
>
  <div class="flex items-start justify-between gap-3">
    <button type="button" class="min-w-0 flex-1 rounded text-left" onclick={() => onopen?.(job.id)}>
      <span class="block truncate text-sm font-medium text-ink">
        {job.title ?? job.source_url ?? job.id}
      </span>
      <span class="mt-0.5 block truncate text-xs text-ink-3">
        {job.source_url ?? job.id}
      </span>
    </button>
    <!-- `compact` keeps the lamp but drops the visible word: the rail and the
         summary line below already name the state, and a screen reader gets
         the word from the badge's own sr-only text. Rendering it three times
         per card made the state text ambiguous to query and read alike. -->
    <StateBadge {state} compact class="shrink-0 pt-0.5" />
  </div>

  <div class="flex flex-col gap-2">
    {#if railVisible(state, stage)}
      <StageRail {state} {stage} {stale} />
    {/if}
    <div class="flex items-baseline justify-between gap-3">
      <span class="text-xs text-ink-3">{stale ? `${summary} · no progress` : summary}</span>
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

  <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-3">
    {#if live?.downloadedBytes != null}
      <span class="fig"
        >{formatBytes(live.downloadedBytes)}{live.totalBytes
          ? ` / ${formatBytes(live.totalBytes)}`
          : ''}</span
      >
    {/if}
    {#if live?.speed != null}
      <span class="fig">{formatBytes(live.speed)}/s</span>
    {/if}
    {#if live?.eta != null}
      <span class="fig">ETA {formatEta(live.eta)}</span>
    {/if}
    {#if job.error_code}
      <span class="text-crit">{job.error_code}: {job.error_message}</span>
    {/if}
    {#if canCancel}
      <!-- Deliberate isolation: the destructive action sits alone at the end of
           the row, with empty space, so it cannot be hit on the way to
           reading the figures. -->
      <Button variant="danger" icon="cancel" class="ml-auto" onclick={() => oncancel?.(job.id)}>
        Cancel
      </Button>
    {/if}
  </div>
</li>
