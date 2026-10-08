import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  // Vitest resolves `svelte` to the server build by default, which makes
  // `mount()` (and every component test) fail with
  // `lifecycle_function_unavailable`. The `browser` condition forces the
  // client build for tests; the production client build already targets the
  // browser, so this changes nothing outside `vitest run`.
  resolve: {
    conditions: ['browser'],
  },
  test: {
    environment: 'jsdom',
  },
  build: {
    // FastAPI serves these assets in production; keep them relative so the app
    // works from any mount path.
    assetsDir: 'assets',
    sourcemap: false,
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    // Dev proxy: the SPA talks to the local service on the same origin so no
    // CORS/loopback allowance is ever needed in development either. Follows
    // LMD_PORT so a non-default service port keeps working. changeOrigin must
    // stay true: the backend rejects any Host whose port is not its own
    // (validate_host expected_port → 403 INVALID_HOST), and with false the
    // backend would see `127.0.0.1:5173` instead of its own port.
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.LMD_PORT ?? 8765}`,
        changeOrigin: true,
      },
    },
  },
})
