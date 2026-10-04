import { copyFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'

const resolvePath = (relative: string) => fileURLToPath(new URL(relative, import.meta.url))

function copyManifest(): Plugin {
  return {
    name: 'lmd:copy-manifest',
    apply: 'build',
    closeBundle() {
      copyFileSync(resolvePath('./src/manifest.json'), resolvePath('./dist/manifest.json'))
    },
  }
}

export default defineConfig({
  plugins: [copyManifest()],
  build: {
    target: 'es2022',
    modulePreload: { polyfill: false },
    rollupOptions: {
      input: {
        popup: resolvePath('./src/popup/index.html'),
        background: resolvePath('./src/background/index.ts'),
      },
      output: {
        // The manifest hardcodes these paths.
        entryFileNames: (chunk) =>
          chunk.name === 'background' ? 'src/background/index.js' : 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
})
