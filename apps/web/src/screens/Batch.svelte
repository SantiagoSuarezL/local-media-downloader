<script lang="ts">
  import type { BatchItemResult } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { PRESETS, findPreset } from '../lib/presets'
  import Button from '../lib/components/Button.svelte'
  import Icon from '../lib/icons/Icon.svelte'

  interface Props {
    onopen?: (id: string) => void
  }

  const { onopen }: Props = $props()

  let text = $state('')
  let selectedPreset = $state(PRESETS[0].id)
  let priority = $state(0)
  let submitting = $state(false)
  let error = $state<string | null>(null)
  let results = $state<BatchItemResult[]>([])

  const urls = $derived(
    text
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0),
  )

  const summary = $derived(
    results.length === 0
      ? null
      : {
          created: results.filter((r) => r.status === 'created').length,
          duplicates: results.filter((r) => r.status === 'duplicate').length,
          errors: results.filter((r) => r.status === 'error').length,
        },
  )

  async function submit(): Promise<void> {
    error = null
    results = []
    if (urls.length === 0) {
      error = 'Paste at least one URL, one per line.'
      return
    }
    if (urls.length > 100) {
      error = 'At most 100 URLs per batch.'
      return
    }
    submitting = true
    try {
      const preset = findPreset(selectedPreset)
      const response = await api.createBatch({
        items: urls.map((url) => ({ url, intent: preset.intent, priority })),
      })
      results = response.results
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      submitting = false
    }
  }
</script>

<section class="flex flex-col gap-6">
  <div class="flex flex-col gap-2">
    <h1 class="text-lg font-semibold text-ink">Batch queue</h1>
    <p class="text-sm text-ink-3">
      One URL per line. Each becomes an independent job; pasting the same link twice creates one
      job, not two. One bad URL never fails the rest.
    </p>
  </div>

  <textarea
    class="min-h-40 rounded-lg border border-seam bg-panel px-3 py-2 font-mono text-sm text-ink outline-none placeholder:text-ink-4 focus:border-accent-dim"
    placeholder="https://… (one URL per line)"
    bind:value={text}></textarea>

  <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
    <select
      aria-label="Output preset"
      class="rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
      bind:value={selectedPreset}
    >
      {#each PRESETS as option (option.id)}
        <option value={option.id}>{option.label}</option>
      {/each}
    </select>
    <label class="flex items-center gap-2 text-sm text-ink-3">
      Priority
      <input
        type="number"
        class="fig w-20 rounded-lg border border-seam bg-panel px-2 py-1.5 text-sm text-ink"
        bind:value={priority}
      />
    </label>
    <Button
      variant="primary"
      icon="batch"
      busy={submitting}
      class="sm:ml-auto"
      onclick={() => void submit()}
    >
      Queue {urls.length} URL{urls.length === 1 ? '' : 's'}
    </Button>
  </div>

  {#if selectedPreset === 'sticker'}
    <p class="text-xs text-ink-3">
      Creates a 512×512 animated WebP (up to 3 seconds and 500 KB). Import into WhatsApp is not
      guaranteed.
    </p>
  {/if}

  {#if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {/if}

  {#if summary}
    <p class="fig text-sm text-ink-2">
      {summary.created} created · {summary.duplicates} duplicates · {summary.errors} errors
    </p>
    <div class="overflow-x-auto rounded-xl border border-seam">
      <table class="w-full text-left text-xs">
        <thead class="bg-panel text-ink-3">
          <tr>
            <th class="px-3 py-2 font-medium">#</th>
            <th class="px-3 py-2 font-medium">Result</th>
            <th class="px-3 py-2 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {#each results as result (result.index)}
            <tr class="border-t border-seam/70">
              <td class="fig px-3 py-2 text-ink-4">{result.index + 1}</td>
              <td class="px-3 py-2">
                {#if result.status === 'created'}
                  <span class="text-ok">queued</span>
                {:else if result.status === 'duplicate'}
                  <span class="text-warn">already queued</span>
                {:else}
                  <span class="text-crit">error</span>
                {/if}
              </td>
              <td class="px-3 py-2">
                {#if result.job}
                  <button
                    type="button"
                    class="max-w-80 truncate rounded text-left text-ink-2 transition-colors hover:text-accent"
                    onclick={() => result.job && onopen?.(result.job.id)}
                  >
                    {result.job.title ?? result.job.id}
                  </button>
                {:else if result.error}
                  <span class="text-crit">
                    {result.error.code}{result.error.message ? `: ${result.error.message}` : ''}
                  </span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
