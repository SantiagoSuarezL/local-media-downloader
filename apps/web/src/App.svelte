<script lang="ts">
  import Batch from './screens/Batch.svelte'
  import Dashboard from './screens/Dashboard.svelte'
  import Diagnostics from './screens/Diagnostics.svelte'
  import History from './screens/History.svelte'
  import JobDetails from './screens/JobDetails.svelte'
  import Resolve from './screens/Resolve.svelte'
  import Settings from './screens/Settings.svelte'
  import Mark from './lib/brand/Mark.svelte'
  import Icon from './lib/icons/Icon.svelte'
  import type { IconName } from './lib/icons/paths'
  import { startLiveUpdates, stopLiveUpdates } from './lib/live'
  import { startJobNotifications } from './lib/notify'

  const TABS = [
    { name: 'Dashboard', icon: 'dashboard' },
    { name: 'Resolve', icon: 'resolve' },
    { name: 'Batch', icon: 'batch' },
    { name: 'Job details', icon: 'job' },
    { name: 'History', icon: 'history' },
    { name: 'Settings', icon: 'settings' },
    { name: 'Diagnostics', icon: 'diagnostics' },
  ] as const satisfies readonly { name: string; icon: IconName }[]
  type Tab = (typeof TABS)[number]['name']

  let tab = $state<Tab>('Dashboard')
  let selectedJobId = $state<string | null>(null)
  let texture = $state<HTMLDivElement | null>(null)

  // Extension handoff contract (Phase 9): the popup opens `/?url=<encoded>` and
  // the app lands on Resolve with the URL prefilled, nothing else needed.
  const handoffUrl = new URLSearchParams(window.location.search).get('url')

  startLiveUpdates()
  startJobNotifications()
  $effect(() => () => stopLiveUpdates())

  $effect(() => {
    if (handoffUrl) {
      tab = 'Resolve'
    }
  })

  /**
   * The ground parallax.
   *
   * Only a transform changes, so the browser never repaints the seam grid -- it
   * re-composites one layer. The listener is passive and coalesced to one
   * frame, so a fast scroll costs one style write per frame rather than one per
   * event, and the work stops entirely under reduced-motion.
   */
  $effect(() => {
    const element = texture
    if (!element) {
      return
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }

    let frame = 0
    const onScroll = (): void => {
      if (frame !== 0) {
        return
      }
      frame = requestAnimationFrame(() => {
        frame = 0
        const offset = Math.min(window.scrollY, 900) * 0.12
        element.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame !== 0) {
        cancelAnimationFrame(frame)
      }
    }
  })

  function openJob(id: string): void {
    selectedJobId = id
    tab = 'Job details'
  }
</script>

<div class="relative min-h-screen">
  <div class="lmd-ground" aria-hidden="true"></div>
  <div class="lmd-texture" bind:this={texture} aria-hidden="true"></div>

  <!-- Solid, not backdrop-blur: a blurred sticky header re-blurs on every
       scroll frame, which is exactly the kind of cost this build refuses. -->
  <header class="sticky top-0 z-10 border-b border-seam bg-well">
    <div class="mx-auto flex max-w-5xl flex-col gap-3 px-6 py-3 sm:flex-row sm:items-center">
      <div class="flex items-center gap-2.5">
        <Mark class="h-7 w-7 shrink-0" />
        <h1 class="text-sm font-semibold tracking-tight text-ink">Local Media Downloader</h1>
      </div>
      <nav class="flex flex-wrap gap-1 sm:ml-auto" aria-label="Sections">
        {#each TABS as entry (entry.name)}
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors duration-150
              {tab === entry.name
              ? 'bg-raised text-ink'
              : 'text-ink-3 hover:bg-panel hover:text-ink-2'}"
            aria-current={tab === entry.name ? 'page' : undefined}
            onclick={() => (tab = entry.name)}
          >
            <Icon name={entry.icon} class="h-3.5 w-3.5 shrink-0" />
            {entry.name}
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
    {:else if tab === 'Batch'}
      <Batch onopen={openJob} />
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
