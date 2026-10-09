<script lang="ts">
  interface Props {
    class?: string
    /** Rows to draw. Matches the shape of the list it stands in for. */
    rows?: number
  }

  const { class: className = '', rows = 3 }: Props = $props()
</script>

<!--
  A skeleton asserts a shape the data will have. Used only where we know the
  content's form (a card, a table row), never over a region whose real state is
  unknown -- an unknown region gets a plain line of text, because a skeleton
  there is a guess dressed as a fact.
-->
<div class="flex flex-col gap-3" role="status" aria-busy="true" aria-label="Loading">
  {#each Array.from({ length: rows }, (_, index) => index) as index (index)}
    <div class="rounded-lg border border-seam bg-panel p-4 {className}">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0 flex-1 space-y-2">
          <div class="h-3 w-2/5 rounded bg-raised"></div>
          <div class="h-2.5 w-4/5 rounded bg-well"></div>
        </div>
        <div class="h-3 w-16 shrink-0 rounded bg-well"></div>
      </div>
      <div class="mt-4 flex gap-1.5">
        <div class="h-1 flex-1 rounded-full bg-well"></div>
        <div class="h-1 flex-1 rounded-full bg-well"></div>
        <div class="h-1 flex-1 rounded-full bg-well"></div>
        <div class="h-1 flex-1 rounded-full bg-well"></div>
      </div>
    </div>
  {/each}
</div>

<style>
  div > div {
    /* Opacity only: the skeletons fade in place and never move a neighbour,
       so nothing reflows while the real content arrives. */
    animation: lmd-rise 1.4s ease-in-out infinite;
  }

  div > div:nth-child(2) {
    animation-delay: 120ms;
  }
  div > div:nth-child(3) {
    animation-delay: 240ms;
  }

  @keyframes lmd-rise {
    0%,
    100% {
      opacity: 0.55;
    }
    50% {
      opacity: 0.9;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    div > div {
      animation: none;
      opacity: 0.75;
    }
  }
</style>
