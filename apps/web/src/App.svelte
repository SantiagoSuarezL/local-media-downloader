<script lang="ts">
  import Dashboard from './screens/Dashboard.svelte'
  import Diagnostics from './screens/Diagnostics.svelte'
  import History from './screens/History.svelte'
  import JobDetails from './screens/JobDetails.svelte'
  import Resolve from './screens/Resolve.svelte'
  import Settings from './screens/Settings.svelte'
  import { startLiveUpdates, stopLiveUpdates } from './lib/live'

  const TABS = [
    'Dashboard',
    'Resolve',
    'Job details',
    'History',
    'Settings',
    'Diagnostics',
  ] as const
  type Tab = (typeof TABS)[number]

  let tab = $state<Tab>('Dashboard')
  let selectedJobId = $state<string | null>(null)

  // Extension handoff contract (Phase 9): the popup opens `/?url=<encoded>` and
  // the app lands on Resolve with the URL prefilled, nothing else needed.
  const handoffUrl = new URLSearchParams(window.location.search).get('url')

  startLiveUpdates()
  $effect(() => () => stopLiveUpdates())

  $effect(() => {
    if (handoffUrl) {
      tab = 'Resolve'
    }
  })

  function openJob(id: string): void {
    selectedJobId = id
    tab = 'Job details'
  }
</script>

<div class="min-h-screen bg-neutral-950 text-neutral-100">
  <header class="border-b border-neutral-800 bg-neutral-900/40">
    <div class="mx-auto flex max-w-5xl flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center">
      <h1 class="text-sm font-semibold tracking-wide text-neutral-100">Local Media Downloader</h1>
      <nav class="flex flex-wrap gap-1 sm:ml-auto">
        {#each TABS as name (name)}
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs {tab === name
              ? 'bg-neutral-800 text-neutral-100'
              : 'text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200'}"
            onclick={() => (tab = name)}
          >
            {name}
          </button>
        {/each}
      </nav>
    </div>
  </header>

  <main class="mx-auto max-w-5xl px-6 py-8">
    {#if tab === 'Dashboard'}
      <Dashboard onopen={openJob} />
    {:else if tab === 'Resolve'}
      <Resolve onstarted={openJob} initialUrl={handoffUrl ?? undefined} />
    {:else if tab === 'Job details'}
      <JobDetails jobId={selectedJobId} oncancelled={() => (tab = 'Dashboard')} />
    {:else if tab === 'History'}
      <History onopen={openJob} />
    {:else if tab === 'Settings'}
      <Settings />
    {:else}
      <Diagnostics />
    {/if}
  </main>
</div>
