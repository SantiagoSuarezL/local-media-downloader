<script lang="ts">
  import { ICON_PATHS, type IconName } from './paths'

  interface Props {
    name: IconName
    class?: string
    /** Kept at one weight so the set never mixes. */
    strokeWidth?: number
  }

  const { name, class: className = 'h-4 w-4', strokeWidth = 1.5 }: Props = $props()
</script>

<svg
  viewBox="0 0 24 24"
  class={className}
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
  data-icon={name}
>
  <!-- eslint-disable-next-line svelte/no-at-html-tags -- registry is a static literal map, not user input -->
  {@html ICON_PATHS[name]}
</svg>
