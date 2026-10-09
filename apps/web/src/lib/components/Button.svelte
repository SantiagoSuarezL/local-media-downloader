<script lang="ts">
  import type { Snippet } from 'svelte'
  import Icon from '../icons/Icon.svelte'
  import type { IconName } from '../icons/paths'
  import Spinner from './Spinner.svelte'

  type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

  interface Props {
    variant?: Variant
    /** A request is in flight. Shows a spinner, marks aria-busy, blocks re-entry. */
    busy?: boolean
    disabled?: boolean
    icon?: IconName
    iconEnd?: IconName
    type?: 'button' | 'submit'
    class?: string
    title?: string
    onclick?: (event: MouseEvent) => void
    children: Snippet
  }

  const {
    variant = 'secondary',
    busy = false,
    disabled = false,
    icon,
    iconEnd,
    type = 'button',
    class: className = '',
    title,
    onclick,
    children,
  }: Props = $props()

  const inactive = $derived(disabled || busy)

  const STYLES: Record<Variant, string> = {
    primary: 'bg-accent text-well hover:bg-accent-strong border-transparent',
    secondary: 'bg-raised text-ink border-seam hover:border-seam-strong',
    ghost: 'bg-transparent text-ink-2 border-transparent hover:bg-raised hover:text-ink',
    danger: 'bg-transparent text-crit border-seam hover:border-crit hover:bg-crit/10',
  }
</script>

<button
  {type}
  {title}
  {onclick}
  disabled={inactive}
  aria-busy={busy || undefined}
  class="inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm
    transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-55
    {STYLES[variant]} {className}"
>
  {#if busy}
    <Spinner />
  {:else if icon}
    <Icon name={icon} class="h-4 w-4 shrink-0" />
  {/if}
  {@render children()}
  {#if !busy && iconEnd}
    <Icon name={iconEnd} class="h-4 w-4 shrink-0" />
  {/if}
</button>
