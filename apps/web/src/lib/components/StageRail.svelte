<script lang="ts">
  import { STAGES, railFor, railSummary, type SegmentStatus } from '../jobState'

  interface Props {
    state: string
    stage?: string | null
    /** The stage has gone quiet past its budget. Stops the pulse and warns. */
    stale?: boolean
    class?: string
  }

  const { state, stage = null, stale = false, class: className = '' }: Props = $props()

  const segments = $derived(railFor(state, stage))
  const summary = $derived(railSummary(state, stage))

  function toneFor(status: SegmentStatus): string {
    if (status === 'done') {
      return 'bg-accent/25'
    }
    if (status === 'failed') {
      return 'bg-crit'
    }
    if (status === 'halted') {
      return 'bg-warn'
    }
    if (status === 'active') {
      // A stale stage must stop looking busy. The whole point of this rail is
      // that it cannot claim progress that is not arriving.
      return stale ? 'bg-warn' : 'bg-accent'
    }
    return 'bg-seam-strong'
  }
</script>

<!--
  The signature move. Four fixed segments for the pipeline, the live one lit.
  It replaces the single progress bar as the primary state readout: a bar says
  how far one stage got, the rail says which stage you are in and whether it is
  still moving.
-->
<ol class="flex w-full items-center gap-1.5 {className}" aria-label="Pipeline: {summary}">
  {#each STAGES as stageDef, index (stageDef.key)}
    {@const status = segments[index]}
    <li
      class="h-1 flex-1 rounded-full {toneFor(status)} {status === 'active' && !stale
        ? 'animate-pulse'
        : ''}"
      title="{stageDef.label}: {status}"
    >
      <span class="sr-only">{stageDef.label}: {status}</span>
    </li>
  {/each}
</ol>

<style>
  li {
    /* Segment fill only ever changes colour, so nothing here triggers layout. */
    transition:
      background-color 300ms ease,
      opacity 300ms ease;
  }

  @media (prefers-reduced-motion: reduce) {
    li {
      animation: none !important;
      transition: none;
    }
  }
</style>
