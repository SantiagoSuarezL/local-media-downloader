<script lang="ts">
  interface Props {
    class?: string
    /** Give the mark an accessible name. Off inside the header, where the
     *  wordmark next to it already names the product. */
    labelled?: boolean
  }

  const { class: className = 'h-7 w-7', labelled = false }: Props = $props()
</script>

<!--
  The mark: the project's established bolt, recolored to the sky accent because
  sky is the committed accent (PRODUCT.md, Brand Commitments). One gradient, no
  filters, no masks - the previous favicon carried 9.5 KB of editor export noise
  for the same silhouette.

  The gradient id is fixed because exactly one instance exists per document. If
  that ever changes, the id has to become unique per instance or both marks will
  paint the first definition.
-->
<svg
  viewBox="0 0 48 48"
  class={className}
  role="img"
  aria-hidden={labelled ? undefined : 'true'}
  aria-label={labelled ? 'Local Media Downloader' : undefined}
>
  <defs>
    <linearGradient id="lmd-mark" x1="6" y1="2" x2="42" y2="46" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#7dd3fc" />
      <stop offset=".55" stop-color="#38bdf8" />
      <stop offset="1" stop-color="#0369a1" />
    </linearGradient>
  </defs>
  <rect width="48" height="48" rx="11" fill="#0e1116" />
  <rect x=".5" y=".5" width="47" height="47" rx="10.5" fill="none" stroke="#2e343f" />
  <path
    fill="url(#lmd-mark)"
    d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"
    transform="translate(0 1.5)"
  />
</svg>
