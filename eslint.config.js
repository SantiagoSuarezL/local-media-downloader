import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import svelte from 'eslint-plugin-svelte'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.venv/**',
      'data/**',
      'graphify-out/**',
      '.agent/**',
      '.claude/**',
      '.opencode/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...svelte.configs['flat/recommended'],
  prettier,
  ...svelte.configs['flat/prettier'],
  {
    languageOptions: {
      globals: { ...globals.browser },
    },
  },
  {
    files: ['**/*.config.ts', '**/*.config.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  {
    // TypeScript inside <script lang="ts"> needs the TS parser wired in
    // explicitly; without it the Svelte parser falls back to espree and every
    // type-only import is a syntax error.
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },
)
