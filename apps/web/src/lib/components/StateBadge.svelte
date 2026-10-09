<script lang="ts">
  import { toneFor } from '../jobState'

  interface Props {
    state: string
    /** Hide the state word and keep only the lamp, for dense rows. */
    compact?: boolean
    class?: string
  }

  const { state, compact = false, class: className = '' }: Props = $props()

  const DOT: Record<string, string> = {
    ok: 'bg-ok',
    warn: 'bg-warn',
    crit: 'bg-crit',
    accent: 'bg-accent',
    idle: 'bg-ink-4',
  }

  const TEXT: Record<string, string> = {
    ok: 'text-ok',
    warn: 'text-warn',
    crit: 'text-crit',
    accent: 'text-accent',
    idle: 'text-ink-3',
  }

  const tone = $derived(toneFor(state))
</script>

<!--
  State is carried by a lamp *and* a word. The lamp alone would fail anyone who
  cannot separate the hues, and the word alone made every row the same weight of
  shouting; together they read as one fact said two ways.
-->
<span class="inline-flex items-center gap-1.5 {className}">
  <span
    class="h-1.5 w-1.5 shrink-0 rounded-full {tone === 'accent' ? 'bg-accent' : DOT[tone]}"
    aria-hidden="true"
  ></span>
  {#if !compact}
    <span class="text-xs font-medium {TEXT[tone]}">{state}</span>
  {/if}
  <span class="sr-only">{state}</span>
</span>
