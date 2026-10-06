<script lang="ts">
  import type { MediaFormatDto, MediaInfoDto, OutputIntent } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { formatBytes, formatDuration } from '../lib/format'

  interface Props {
    onstarted?: (jobId: string) => void
    /** Deep link from the browser extension: `?url=…` prefills the field. */
    initialUrl?: string
  }

  const { onstarted, initialUrl }: Props = $props()

  interface Preset {
    id: string
    label: string
    intent: OutputIntent
  }

  const baseIntent = (overrides: Partial<OutputIntent> = {}): OutputIntent => ({
    media: 'video',
    quality: 'best',
    container: 'mp4',
    audio: 'include',
    video_codec: 'source',
    processing: { resize: null, trim: null },
    ...overrides,
  })

  const presets: Preset[] = [
    { id: 'best', label: 'Best available', intent: baseIntent() },
    { id: 'mp4', label: 'MP4', intent: baseIntent({ container: 'mp4' }) },
    {
      id: 'mp3',
      label: 'MP3',
      intent: baseIntent({ media: 'audio', container: 'mp3', audio: 'only' }),
    },
    {
      id: 'video-only',
      label: 'Video only',
      intent: baseIntent({ container: 'mp4', audio: 'remove' }),
    },
    {
      id: 'no-audio',
      label: 'No audio',
      intent: baseIntent({ container: 'mp4', audio: 'remove' }),
    },
    { id: 'webm', label: 'WebM', intent: baseIntent({ container: 'webm' }) },
    {
      id: 'mkv',
      label: 'MKV',
      intent: baseIntent({ container: 'mkv' }),
    },
    {
      id: 'm4a',
      label: 'M4A (audio only)',
      intent: baseIntent({ media: 'audio', container: 'm4a', audio: 'only' }),
    },
  ]

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
    <h1 class="text-lg font-semibold text-neutral-100">Resolve a URL</h1>
    <p class="text-sm text-neutral-500">
      The local service extracts metadata and plans the download. Nothing leaves this machine.
    </p>
  </div>

  <div class="flex flex-col gap-3 sm:flex-row">
    <input
      type="url"
      class="flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-sky-600"
      placeholder="https://..."
      bind:value={url}
      onkeydown={(event) => event.key === 'Enter' && void resolve()}
    />
    <button
      type="button"
      class="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
      disabled={resolving}
      onclick={() => void resolve()}
    >
      {resolving ? 'Resolving…' : 'Resolve'}
    </button>
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {/if}

  {#if media}
    <article class="flex flex-col gap-4 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
      <div class="flex gap-4">
        {#if media.thumbnail_url}
          <img
            src={media.thumbnail_url}
            alt=""
            referrerpolicy="no-referrer"
            class="h-24 w-40 shrink-0 rounded-lg object-cover"
          />
        {/if}
        <div class="min-w-0">
          <h2 class="truncate text-base font-semibold text-neutral-100">
            {media.source.title ?? 'Untitled'}
          </h2>
          <p class="mt-1 text-xs text-neutral-500">
            {media.source.uploader ?? media.source.extractor ?? 'Unknown source'}
          </p>
          <p class="mt-1 text-xs text-neutral-500">{formatDuration(media.duration_seconds)}</p>
          {#if media.is_live}
            <p class="mt-1 text-xs text-amber-400">Live stream</p>
          {/if}
        </div>
      </div>

      {#if media.warnings.length > 0}
        <ul class="flex flex-col gap-1">
          {#each media.warnings as warning (warning)}
            <li class="text-xs text-amber-400">{warning}</li>
          {/each}
        </ul>
      {/if}

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-neutral-400">
          <thead class="text-neutral-500">
            <tr>
              <th class="py-1 pr-3">Format</th>
              <th class="py-1 pr-3">Kind</th>
              <th class="py-1 pr-3">Resolution</th>
              <th class="py-1 pr-3">Codec</th>
              <th class="py-1 pr-3">Size</th>
            </tr>
          </thead>
          <tbody>
            {#each formats.slice(0, 12) as format (format.id)}
              <tr class="border-t border-neutral-800">
                <td class="py-1 pr-3 text-neutral-200">{format.id}</td>
                <td class="py-1 pr-3">{format.kind}</td>
                <td class="py-1 pr-3">
                  {format.height ? `${format.width ?? '?'}x${format.height}` : '—'}
                </td>
                <td class="py-1 pr-3">
                  {format.video_codec ?? '—'}{format.audio_codec ? ` / ${format.audio_codec}` : ''}
                </td>
                <td class="py-1 pr-3">
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

      <div class="flex flex-col gap-3 border-t border-neutral-800 pt-4 sm:flex-row sm:items-center">
        <select
          class="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
          bind:value={selectedPreset}
        >
          {#each presets as option (option.id)}
            <option value={option.id}>{option.label}</option>
          {/each}
        </select>
        <button
          type="button"
          class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 sm:ml-auto"
          disabled={starting}
          onclick={() => void start()}
        >
          {starting ? 'Starting…' : `Start: ${preset.label}`}
        </button>
      </div>
    </article>
  {/if}
</section>
