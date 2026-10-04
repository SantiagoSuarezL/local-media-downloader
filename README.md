# local-media-downloader

Download and transform media locally from almost any supported URL.

Local-first modular monolith with a durable job scheduler. See `docs/` for the
product requirements, architecture, technical spec, engineering principles and
the phased implementation plan.

## Development setup

Requires [uv](https://docs.astral.sh/uv/), Node.js >= 22 and pnpm.

```bash
uv sync                    # Python env + editable apps/api
pnpm install               # JS workspace (web, extension, contracts)
uv run pre-commit install   # git hooks: ruff + prettier on every commit
```

## Checks

Run the same gates as CI before pushing:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright && uv run pytest
pnpm lint && pnpm format:check && pnpm check && pnpm test && pnpm build
```

The `pre-commit` hooks mirror the first two groups, so most failures surface
before the commit is created.

## Layout

```text
apps/api         FastAPI + Granian service, job scheduler, execution adapters
apps/web         Svelte 5 + Vite + Tailwind dashboard (static assets)
apps/extension   Manifest V3 extension with a thin browser adapter
packages/contracts  Shared API contract types
docs/            Product and architecture specs
data/            Runtime data (git-ignored): app.db, jobs, cache, logs
```

`data/`, `dist/`, `.venv/`, `node_modules/`, `.claude/`, `.opencode/` and
`graphify-out/` are git-ignored. `uv.lock` and `pnpm-lock.yaml` are versioned.