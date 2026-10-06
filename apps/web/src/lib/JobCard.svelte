<script lang="ts">
  import type { JobDto } from '@lmd/contracts'
  import { STATE_TONE, formatBytes, formatEta } from '../lib/format'
  import type { LiveJob } from '../lib/live'

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
  const canCancel = $derived(cancellable && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(state))
</script>

<li class="flex flex-col gap-2 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
  <div class="flex items-start justify-between gap-3">
    <button type="button" class="min-w-0 flex-1 text-left" onclick={() => onopen?.(job.id)}>
      <span class="block truncate text-sm font-medium text-neutral-100">
        {job.title ?? job.source_url ?? job.id}
      </span>
      <span class="mt-0.5 block truncate text-xs text-neutral-500">
        {job.source_url ?? job.id}
      </span>
    </button>
    <span
      class="shrink-0 text-xs font-semibold tracking-wide {STATE_TONE[state] ?? 'text-neutral-400'}"
    >
      {state}
    </span>
  </div>

  <div class="h-1.5 w-full overflow-hidden rounded-full bg-neutral-800">
    <div
      class="h-full rounded-full bg-sky-500 transition-[width] duration-300"
      style="width: {Math.min(percent, 100)}%"
    ></div>
  </div>

  <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-500">
    <span>{percent}%</span>
    {#if live?.downloadedBytes != null}
      <span
        >{formatBytes(live.downloadedBytes)}{live.totalBytes
          ? ` / ${formatBytes(live.totalBytes)}`
          : ''}</span
      >
    {/if}
    {#if live?.speed != null}
      <span>{formatBytes(live.speed)}/s</span>
    {/if}
    {#if live?.eta != null}
      <span>ETA {formatEta(live.eta)}</span>
    {/if}
    {#if job.error_code}
      <span class="text-red-400">{job.error_code}: {job.error_message}</span>
    {/if}
    {#if canCancel}
      <button
        type="button"
        class="ml-auto rounded border border-neutral-700 px-2 py-0.5 text-neutral-300 hover:bg-neutral-800"
        onclick={() => oncancel?.(job.id)}
      >
        Cancel
      </button>
    {/if}
  </div>
</li>
