import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
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
    // LMD_PORT so a non-default service port keeps working.
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.LMD_PORT ?? 8765}`,
        changeOrigin: false,
      },
    },
  },
})
