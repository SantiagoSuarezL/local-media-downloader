<script lang="ts">
  import type { HealthDto } from '@lmd/contracts'
  import { api } from '../lib/api'

  let health = $state<HealthDto | null>(null)
  let error = $state<string | null>(null)

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
    <h1 class="text-lg font-semibold text-neutral-100">Diagnostics</h1>
    <p class="mt-1 text-sm text-neutral-500">
      Detection only reports presence and version; tools are never updated automatically.
    </p>
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {:else if !health}
    <p class="text-sm text-neutral-500">Loading…</p>
  {:else}
    <dl class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {#each rows as [label, value] (label)}
        <div class="rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2">
          <dt class="text-xs text-neutral-500">{label}</dt>
          <dd class="mt-0.5 text-sm break-all text-neutral-100">{value}</dd>
        </div>
      {/each}
    </dl>

    <h2 class="text-sm font-semibold text-neutral-200">Tools</h2>
    <div class="overflow-x-auto rounded-xl border border-neutral-800">
      <table class="w-full text-left text-xs">
        <thead class="bg-neutral-900/60 text-neutral-500">
          <tr>
            <th class="px-3 py-2">Tool</th>
            <th class="px-3 py-2">Detected</th>
            <th class="px-3 py-2">Version</th>
          </tr>
        </thead>
        <tbody>
          {#each Object.entries(health.tools) as [name, tool] (name)}
            <tr class="border-t border-neutral-800/80">
              <td class="px-3 py-2 text-neutral-200">{name}</td>
              <td class="px-3 py-2 {tool.detected ? 'text-emerald-400' : 'text-red-400'}">
                {tool.detected ? 'yes' : 'no'}
              </td>
              <td class="px-3 py-2 text-neutral-400">{tool.version ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2">
      <p class="text-xs text-neutral-500">Extractor</p>
      <p class="mt-0.5 text-sm text-neutral-100">
        {health.extractor.name}
        {health.extractor.version ?? ''}
      </p>
      {#if health.extractor.may_be_outdated}
        <p class="mt-1 text-xs text-amber-400">
          This extractor set may be outdated for some sites.
        </p>
      {/if}
    </div>
  {/if}
</section>
