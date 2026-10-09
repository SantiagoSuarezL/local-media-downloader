<script lang="ts">
  interface Props {
    class?: string
    label?: string
  }

  const { class: className = 'h-3.5 w-3.5', label }: Props = $props()
</script>

<!--
  A spinner is a claim: it says work is happening right now. That is only
  honest where a request is genuinely in flight, which is why this is used
  beside a disabled control and never as a placeholder over content whose
  freshness is unknown. Rotation is a transform, so it stays on the compositor.
-->
<svg
  class={className}
  viewBox="0 0 24 24"
  fill="none"
  aria-hidden="true"
  role={label ? 'status' : undefined}
>
  {#if label}
    <title>{label}</title>
  {/if}
  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity="0.22" stroke-width="3" />
  <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
</svg>

<style>
  svg {
    animation: lmd-spin 0.7s linear infinite;
  }

  @keyframes lmd-spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Reduced motion keeps the ring visible but stops it turning: the shape
     still reads as "busy" without the movement. */
  @media (prefers-reduced-motion: reduce) {
    svg {
      animation-duration: 2.4s;
    }
  }
</style>
