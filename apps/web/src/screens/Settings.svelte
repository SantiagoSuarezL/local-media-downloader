<script lang="ts">
  import type { SettingsDto } from '@lmd/contracts'
  import { api } from '../lib/api'

  let settings = $state<SettingsDto | null>(null)
  let error = $state<string | null>(null)

  $effect(() => {
    api
      .settings()
      .then((loaded) => {
        settings = loaded
        error = null
      })
      .catch((err: unknown) => {
        error = err instanceof Error ? err.message : String(err)
      })
  })

  const rows = $derived(
    settings
      ? ([
          ['Host', settings.host],
          ['Port', String(settings.port)],
          ['Log level', settings.log_level],
          ['Data directory', settings.data_dir],
          ['Database', settings.database_path],
          ['Max active jobs', String(settings.scheduler_max_active)],
          ['Max concurrent downloads', String(settings.scheduler_max_downloads)],
          ['Max concurrent encoders', String(settings.scheduler_max_encoders)],
          ['Max attempts', String(settings.scheduler_max_attempts)],
          ['Retry backoff (s)', String(settings.scheduler_retry_backoff_seconds)],
        ] as const)
      : [],
  )
</script>

<section class="flex flex-col gap-6">
  <div>
    <h1 class="text-lg font-semibold text-neutral-100">Settings</h1>
    <p class="mt-1 text-sm text-neutral-500">
      Configuration is environment-driven (LMD_*) and read-only at runtime; restart the service to
      apply changes.
    </p>
  </div>

  {#if error}
    <p class="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
      {error}
    </p>
  {:else if !settings}
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
  {/if}
</section>
