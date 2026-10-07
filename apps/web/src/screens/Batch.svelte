<script lang="ts">
  import type { BatchItemResult } from '@lmd/contracts'
  import { api } from '../lib/api'
  import { PRESETS, findPreset } from '../lib/presets'

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
    <h1 class="text-lg font-semibold text-neutral-100">Batch queue</h1>
    <p class="text-sm text-neutral-500">
      One URL per line. Each becomes an independent job; pasting the same link twice creates one
      job, not two. One bad URL never fails the rest.
    </p>
  </div>

  <textarea
    class="min-h-40 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 font-mono text-sm text-neutral-100 outline-none focus:border-sky-600"
    placeholder="https://… (one URL per line)"
    bind:value={text}></textarea>

  <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
    <select
      class="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
      bind:value={selectedPreset}
    >
      {#each PRESETS as option (option.id)}
        <option value={option.id}>{option.label}</option>
      {/each}
    </select>
    <label class="flex items-center gap-2 text-sm text-neutral-400">
      Priority
      <input
        type="number"
        class="w-20 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
        bind:value={priority}
      />
    </label>
    <button
      type="button"
      class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 sm:ml-auto"
      disabled={submitting}
      onclick={() => void submit()}
    >
      {submitting ? 'Queueing…' : `Queue ${urls.length} URL${urls.length === 1 ? '' : 's'}`}
    </button>
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {/if}

  {#if summary}
    <p class="text-sm text-neutral-400">
      {summary.created} created · {summary.duplicates} duplicates · {summary.errors} errors
    </p>
    <div class="overflow-x-auto rounded-xl border border-neutral-800">
      <table class="w-full text-left text-xs">
        <thead class="bg-neutral-900/60 text-neutral-500">
          <tr>
            <th class="px-3 py-2">#</th>
            <th class="px-3 py-2">Result</th>
            <th class="px-3 py-2">Detail</th>
          </tr>
        </thead>
        <tbody>
          {#each results as result (result.index)}
            <tr class="border-t border-neutral-800/80">
              <td class="px-3 py-2 text-neutral-500">{result.index + 1}</td>
              <td class="px-3 py-2">
                {#if result.status === 'created'}
                  <span class="text-emerald-400">queued</span>
                {:else if result.status === 'duplicate'}
                  <span class="text-amber-400">already queued</span>
                {:else}
                  <span class="text-red-400">error</span>
                {/if}
              </td>
              <td class="px-3 py-2">
                {#if result.job}
                  <button
                    type="button"
                    class="max-w-80 truncate text-left text-neutral-200 hover:text-sky-300"
                    onclick={() => result.job && onopen?.(result.job.id)}
                  >
                    {result.job.title ?? result.job.id}
                  </button>
                {:else if result.error}
                  <span class="text-red-400">
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
