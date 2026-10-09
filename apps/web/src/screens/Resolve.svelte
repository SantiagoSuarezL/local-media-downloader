<script lang="ts">
  import type { MediaFormatDto, MediaInfoDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { formatBytes, formatDuration } from '../lib/format'
  import { PRESETS } from '../lib/presets'
  import Button from '../lib/components/Button.svelte'
  import Icon from '../lib/icons/Icon.svelte'

  interface Props {
    onstarted?: (jobId: string) => void
    /** Deep link from the browser extension: `?url=…` prefills the field. */
    initialUrl?: string
  }

  const { onstarted, initialUrl }: Props = $props()

  const presets = PRESETS

  let url = $state('')
  let media = $state<MediaInfoDto | null>(null)
  let resolving = $state(false)
  let starting = $state(false)
  let error = $state<string | null>(null)
  let selectedPreset = $state(presets[0].id)

  // Extension handoff: prefill once per incoming URL. The effect depends only
  // on `initialUrl`, so later manual edits are never overwritten.
  $effect(() => {
    if (initialUrl && initialUrl !== url) {
      url = initialUrl
    }
  })

  const preset = $derived(presets.find((p) => p.id === selectedPreset) ?? presets[0])
  const formats = $derived<MediaFormatDto[]>(media?.formats ?? [])

  async function resolve(): Promise<void> {
    error = null
    media = null
    if (!url.trim()) {
      error = 'Paste a media URL first.'
      return
    }
    resolving = true
    try {
      media = await api.resolve(url.trim())
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      resolving = false
    }
  }

  async function start(): Promise<void> {
    error = null
    starting = true
    try {
      const job = await api.createJob({
        url: url.trim(),
        intent: preset.intent,
        title: media?.source.title ?? undefined,
      })
      onstarted?.(job.id)
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      starting = false
    }
  }
</script>

<section class="flex flex-col gap-6">
  <div class="flex flex-col gap-2">
    <h1 class="text-lg font-semibold text-ink">Resolve a URL</h1>
    <p class="text-sm text-ink-3">
      The local service extracts metadata and plans the download. Nothing leaves this machine.
    </p>
  </div>

  <div class="flex flex-col gap-3 sm:flex-row">
    <input
      type="url"
      class="flex-1 rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-4 focus:border-accent-dim"
      placeholder="https://..."
      bind:value={url}
      onkeydown={(event) => event.key === 'Enter' && void resolve()}
    />
    <Button variant="primary" icon="resolve" busy={resolving} onclick={() => void resolve()}>
      Resolve
    </Button>
  </div>

  {#if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {/if}

  {#if media}
    <article class="flex flex-col gap-4 rounded-xl border border-seam bg-panel p-4">
      <div class="flex gap-4">
        {#if media.thumbnail_url}
          <img
            src={media.thumbnail_url}
            alt=""
            width="160"
            height="96"
            referrerpolicy="no-referrer"
            class="h-24 w-40 shrink-0 rounded-lg object-cover"
          />
        {/if}
        <div class="min-w-0">
          <h2 class="truncate text-base font-semibold text-ink">
            {media.source.title ?? 'Untitled'}
          </h2>
          <p class="mt-1 text-xs text-ink-3">
            {media.source.uploader ?? media.source.extractor ?? 'Unknown source'}
          </p>
          <p class="fig mt-1 text-xs text-ink-3">{formatDuration(media.duration_seconds)}</p>
          {#if media.is_live}
            <p class="mt-1 flex items-center gap-1.5 text-xs text-warn">
              <span class="h-1.5 w-1.5 rounded-full bg-warn" aria-hidden="true"></span>
              Live stream
            </p>
          {/if}
        </div>
      </div>

      {#if media.warnings.length > 0}
        <ul class="flex flex-col gap-1">
          {#each media.warnings as warning (warning)}
            <li class="flex items-start gap-1.5 text-xs text-warn">
              <Icon name="alert" class="mt-px h-3 w-3 shrink-0" />
              {warning}
            </li>
          {/each}
        </ul>
      {/if}

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-ink-3">
          <thead class="text-ink-3">
            <tr>
              <th class="py-1 pr-3 font-medium">Format</th>
              <th class="py-1 pr-3 font-medium">Kind</th>
              <th class="py-1 pr-3 font-medium">Resolution</th>
              <th class="py-1 pr-3 font-medium">Codec</th>
              <th class="py-1 pr-3 font-medium">Size</th>
            </tr>
          </thead>
          <tbody>
            {#each formats.slice(0, 12) as format (format.id)}
              <tr class="border-t border-seam">
                <td class="py-1 pr-3 text-ink-2">{format.id}</td>
                <td class="py-1 pr-3">{format.kind}</td>
                <td class="fig py-1 pr-3">
                  {format.height ? `${format.width ?? '?'}x${format.height}` : '—'}
                </td>
                <td class="py-1 pr-3">
                  {format.video_codec ?? '—'}{format.audio_codec ? ` / ${format.audio_codec}` : ''}
                </td>
                <td class="fig py-1 pr-3">
                  {format.filesize != null
                    ? formatBytes(format.filesize)
                    : format.filesize_approx
                      ? '~unknown'
                      : '—'}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="flex flex-col gap-3 border-t border-seam pt-4 sm:flex-row sm:items-center">
        <select
          aria-label="Output preset"
          class="rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
          bind:value={selectedPreset}
        >
          {#each presets as option (option.id)}
            <option value={option.id}>{option.label}</option>
          {/each}
        </select>
        <Button
          variant="primary"
          icon="start"
          busy={starting}
          class="sm:ml-auto"
          onclick={() => void start()}
        >
          Start: {preset.label}
        </Button>
      </div>
      {#if selectedPreset === 'sticker'}
        <p class="text-xs text-ink-3">
          Creates a 512×512 animated WebP (up to 3 seconds and 500 KB). Import into WhatsApp is not
          guaranteed.
        </p>
      {/if}
    </article>
  {/if}
</section>
