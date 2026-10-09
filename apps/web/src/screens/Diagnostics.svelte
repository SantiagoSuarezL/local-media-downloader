<script lang="ts">
  import type { HealthDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import Icon from '../lib/icons/Icon.svelte'
  import Spinner from '../lib/components/Spinner.svelte'

  let health = $state<HealthDto | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(true)

  $effect(() => {
    api
      .health()
      .then((loaded) => {
        health = loaded
        error = null
      })
      .catch((err: unknown) => {
        error = err instanceof Error ? err.message : String(err)
      })
      .finally(() => {
        loading = false
      })
  })

  const rows = $derived(
    health
      ? ([
          ['Service', health.status === 'ok' ? 'ok' : 'degraded'],
          ['Version', health.version],
          ['API', health.api],
          ['Database', `${health.database.status} · ${health.database.detail}`],
          ['Storage', `${health.storage.status} · ${health.storage.detail}`],
        ] as const)
      : [],
  )
</script>

<section class="flex flex-col gap-6">
  <div>
    <h1 class="text-lg font-semibold text-ink">Diagnostics</h1>
    <p class="mt-1 text-sm text-ink-3">
      Detection only reports presence and version; tools are never updated automatically.
    </p>
  </div>

  {#if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {:else if !health && loading}
    <div class="flex items-center gap-2 text-sm text-ink-3" role="status" aria-busy="true">
      <Spinner />
      Detecting tools. The first health check after startup spawns each tool once, so it can take a few
      seconds.
    </div>
  {:else if health}
    <dl class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {#each rows as [label, value] (label)}
        <div class="rounded-lg border border-seam bg-panel px-3 py-2">
          <dt class="text-xs text-ink-3">{label}</dt>
          <dd class="mt-0.5 text-sm break-all text-ink">{value}</dd>
        </div>
      {/each}
    </dl>

    <h2 class="text-sm font-semibold text-ink-2">Tools</h2>
    <div class="overflow-x-auto rounded-xl border border-seam">
      <table class="w-full text-left text-xs">
        <thead class="bg-panel text-ink-3">
          <tr>
            <th class="px-3 py-2 font-medium">Tool</th>
            <th class="px-3 py-2 font-medium">Detected</th>
            <th class="px-3 py-2 font-medium">Version</th>
          </tr>
        </thead>
        <tbody>
          {#each Object.entries(health.tools) as [name, tool] (name)}
            <tr class="border-t border-seam/70">
              <td class="px-3 py-2 text-ink-2">{name}</td>
              <!-- Lamp plus word: "no" is a critical fact here (it decides
                   whether a download can work), so it gets the failure colour
                   and never relies on the colour alone. -->
              <td class="px-3 py-2">
                <span class="inline-flex items-center gap-1.5">
                  <span
                    class="h-1.5 w-1.5 rounded-full {tool.detected ? 'bg-ok' : 'bg-crit'}"
                    aria-hidden="true"
                  ></span>
                  <span class={tool.detected ? 'text-ok' : 'text-crit'}>
                    {tool.detected ? 'yes' : 'no'}
                  </span>
                </span>
              </td>
              <td class="fig px-3 py-2 text-ink-3">{tool.version ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="rounded-lg border border-seam bg-panel px-3 py-2">
      <p class="text-xs text-ink-3">Extractor</p>
      <p class="mt-0.5 text-sm text-ink">
        {health.extractor.name}
        {health.extractor.version ?? ''}
      </p>
      {#if health.extractor.may_be_outdated}
        <p class="mt-1 flex items-start gap-1.5 text-xs text-warn">
          <Icon name="alert" class="mt-px h-3 w-3 shrink-0" />
          This extractor set may be outdated for some sites.
        </p>
      {/if}
    </div>
  {/if}
</section>
