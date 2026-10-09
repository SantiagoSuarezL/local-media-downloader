<script lang="ts">
  import type { SettingsDto } from '@lmd/contracts'
  import { api } from '../lib/api'
  import {
    notificationsEnabled,
    requestNotificationPermission,
    setNotificationsEnabled,
  } from '../lib/notify'
  import Button from '../lib/components/Button.svelte'
  import Icon from '../lib/icons/Icon.svelte'
  import Spinner from '../lib/components/Spinner.svelte'

  let settings = $state<SettingsDto | null>(null)
  let error = $state<string | null>(null)
  let saving = $state(false)
  let saved = $state(false)
  let notify = $state(notificationsEnabled())

  // Editable copies of the runtime-tunable keys.
  let urlRetention = $state('')
  let historyDays = $state(30)
  let tempHours = $state(24)
  let outputRule = $state('flat')

  async function load(): Promise<void> {
    try {
      settings = await api.settings()
      urlRetention = settings.source_url_retention
      historyDays = settings.history_retention_days
      tempHours = settings.temporary_retention_hours
      outputRule = settings.output_rule
      error = null
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  $effect(() => {
    void load()
  })

  async function save(): Promise<void> {
    saving = true
    saved = false
    try {
      settings = await api.updateSettings({
        source_url_retention: urlRetention,
        history_retention_days: historyDays,
        temporary_retention_hours: tempHours,
        output_rule: outputRule,
      })
      error = null
      saved = true
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    } finally {
      saving = false
    }
  }

  async function toggleNotify(enabled: boolean): Promise<void> {
    if (enabled && !(await requestNotificationPermission())) {
      return
    }
    setNotificationsEnabled(enabled)
    notify = notificationsEnabled()
  }

  const bootRows = $derived(
    settings
      ? ([
          ['Host', settings.host],
          ['Port', String(settings.port)],
          ['Log level', settings.log_level],
          ['Data directory', settings.data_dir],
          ['Database', settings.database_path],
          ['Output root', settings.output_root],
          ['Max active jobs', String(settings.scheduler_max_active)],
          ['Max concurrent downloads', String(settings.scheduler_max_downloads)],
          ['Max concurrent encoders', String(settings.scheduler_max_encoders)],
          ['Max attempts', String(settings.scheduler_max_attempts)],
          ['Retry backoff (s)', String(settings.scheduler_retry_backoff_seconds)],
          [
            'Bandwidth limit',
            settings.bandwidth_limit_bps == null
              ? 'unlimited (reserved, not enforced yet)'
              : `${settings.bandwidth_limit_bps} B/s (reserved, not enforced yet)`,
          ],
        ] as const)
      : [],
  )

  const dirty = $derived(
    settings !== null &&
      (urlRetention !== settings.source_url_retention ||
        historyDays !== settings.history_retention_days ||
        tempHours !== settings.temporary_retention_hours ||
        outputRule !== settings.output_rule),
  )
</script>

<section class="flex flex-col gap-6">
  <div>
    <h1 class="text-lg font-semibold text-ink">Settings</h1>
    <p class="mt-1 text-sm text-ink-3">
      Retention and output rules apply at runtime. Host, port, scheduler budgets and the output root
      are boot configuration (LMD_*) and need a restart.
    </p>
  </div>

  {#if error}
    <p
      class="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <Icon name="alert" class="mt-px h-4 w-4 shrink-0" />
      {error}
    </p>
  {:else if !settings}
    <div class="flex items-center gap-2 text-sm text-ink-3" role="status" aria-busy="true">
      <Spinner /> Loading settings…
    </div>
  {:else}
    <div class="rounded-xl border border-seam bg-panel p-4">
      <h2 class="text-sm font-semibold text-ink-2">Retention & output</h2>
      <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label class="flex flex-col gap-1 text-xs text-ink-3">
          Keep full source URLs
          <select
            class="rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
            bind:value={urlRetention}
          >
            <option value="immediately">Redact immediately</option>
            <option value="7days">7 days (default)</option>
            <option value="30days">30 days</option>
            <option value="never">Never redact</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-xs text-ink-3">
          Output folder rule
          <select
            class="rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
            bind:value={outputRule}
          >
            <option value="flat">Flat: Title.ext</option>
            <option value="by_extractor">By site: site/Title.ext</option>
            <option value="by_date">By date: YYYY/MM/Title.ext</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-xs text-ink-3">
          Keep finished jobs (days)
          <input
            type="number"
            min="0"
            class="fig rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
            bind:value={historyDays}
          />
        </label>
        <label class="flex flex-col gap-1 text-xs text-ink-3">
          Keep temporary artifacts (hours)
          <input
            type="number"
            min="0"
            class="fig rounded-lg border border-seam bg-panel px-3 py-2 text-sm text-ink"
            bind:value={tempHours}
          />
        </label>
      </div>
      <div class="mt-3 flex items-center gap-3">
        <Button variant="primary" busy={saving} disabled={!dirty} onclick={() => void save()}>
          Save retention settings
        </Button>
        {#if saved && !dirty}
          <span class="flex items-center gap-1.5 text-xs text-ok" role="status">
            <Icon name="check" class="h-3.5 w-3.5" />
            Saved.
          </span>
        {/if}
      </div>
    </div>

    <div class="rounded-xl border border-seam bg-panel p-4">
      <h2 class="text-sm font-semibold text-ink-2">Desktop notifications</h2>
      <p class="mt-1 text-xs text-ink-3">
        Announce completed and failed jobs with a system notification. No account, no dependency —
        the dashboard is already running here.
      </p>
      <label class="mt-3 flex items-center gap-2 text-sm text-ink-2">
        <input
          type="checkbox"
          class="accent-accent"
          checked={notify}
          onchange={(event) => void toggleNotify(event.currentTarget.checked)}
        />
        Notify me when jobs finish
      </label>
    </div>

    <div>
      <h2 class="text-sm font-semibold text-ink-2">Boot configuration (read-only)</h2>
      <dl class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {#each bootRows as [label, value] (label)}
          <div class="rounded-lg border border-seam bg-panel px-3 py-2">
            <dt class="text-xs text-ink-3">{label}</dt>
            <dd class="mt-0.5 text-sm break-all text-ink">{value}</dd>
          </div>
        {/each}
      </dl>
    </div>
  {/if}
</section>
