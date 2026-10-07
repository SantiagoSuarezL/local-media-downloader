# Testing and quality gates

This document is the executable contract for code changes. It exists for one
reason: **a cheap model writes the code, runs these gates, and either everything
is green or the session stops here** (see §4). It is the companion to
TECHNICAL_SPEC §24 (what must be tested) — this file says *how*, *in what
order*, and *what to do when red*.

## 1. Gate order

Run backend gates first, then frontend gates. Stop at the first red gate.

### Backend (`apps/api`)

```bash
uv run ruff check . && uv run ruff format --check .   # lint + format
uv run pyright                                        # types (the only Python checker, §5)
uv run pytest -m "not smoke"                         # fast suite (all phases, hermetic)
uv run pytest -m smoke                                # live server process + restart (slower)
```

`uv run pytest` runs everything (fast + smoke). CI runs the full suite on
`ubuntu-latest` + `windows-latest`.

### Frontend (`apps/web`, `apps/extension`, `packages/contracts`)

```bash
pnpm lint             # ESLint (JS/TS/Svelte)
pnpm format:check     # Prettier (includes .svelte, yaml, lockfiles-adjacent files)
pnpm check            # svelte-check + tsc (extension) — the TypeScript gate
pnpm -r test          # Vitest: extension (22) + web (85); web has no test runner
                      # besides this — if it is green, the frontend is tested
pnpm build            # both bundles compile (what FastAPI serves / what ships)
```

The root `pnpm test` script is `uv run pytest && pnpm -r test`: the whole
project in one command. CI mirrors it exactly (`.github/workflows/ci.yml`).

## 2. Test inventory (what covers what)

| Suite | File(s) | Covers |
|---|---|---|
| Backend unit + API | `apps/api/tests/test_*.py` (excl. below) | domain (urls, dedupe, output, planner, state machine), adapters (yt-dlp, ffmpeg, ffprobe), scheduler, recovery, retention, security (53 tests), SSE generator |
| Backend contracts | `apps/api/tests/test_contracts.py` | **Every `ErrorCode` has an explicit HTTP status** (no silent 500 — Regla 10.1); exact top-level key sets of every DTO (`_job_dict`, list, batch, cleanup, health, settings, `MediaInfo`); one shared error envelope on all error paths |
| Backend smoke (live) | `apps/api/tests/test_smoke_e2e.py` (`-m smoke`) | Boots the real entrypoint (`python -m local_media_downloader` → Granian) on a fresh port + temp data dir; token handoff via shell `<meta>` + HttpOnly cookie; full status matrix over real HTTP; per-item batch isolation; persistence across a full process restart (same token, same rows) |
| Backend live network | `apps/api/tests/test_ytdlp_live.py` | Opt-in only (`LMD_LIVE_NETWORK=1`); real yt-dlp against public test media. Never runs by default or in CI |
| Extension unit | `apps/extension/tests/*.test.ts` | loopback-only URL validation, health client, manifest least-privilege |
| Web unit (lib) | `apps/web/tests/{api,live,notify,format,presets}.test.ts` | token header injection + error-message extraction; SSE ingest/merge/clamp; notification opt-in + terminal-only announce; formatters; preset validity against the backend intent parser |
| Web contracts | `apps/web/tests/schemas.{ts,test.ts}` | Zod `.strict()` schemas over the same DTOs as `test_contracts.py` — a renamed/dropped/added key fails here. `zod` is a devDependency: it never ships to the dashboard bundle |
| Web components | `apps/web/tests/{JobCard,Batch}.test.ts` | Cancel-button visibility per state (locks the Fase 8 fix); batch parsing/limits/submit/results table |

Backend + frontend contracts are two halves of one rule: **when a DTO changes
on purpose, update `test_contracts.py` AND `tests/schemas.ts` together.** If
only one side is updated, the red side is telling the truth.

## 3. Coverage expectations per change

- New `ErrorCode` → add it to `_STATUS_BY_CODE` in the same commit; the
  exhaustive test in `test_contracts.py` fails otherwise (Regla 10.1).
- New endpoint or changed response shape → extend `test_contracts.py` (key
  sets) and the matching Zod schema + payload in `apps/web/tests/`.
- New web lib function or screen → Vitest file next to it in `apps/web/tests/`.
- New preset/intent value → `tests/presets.test.ts` (it mirrors what the
  backend `parse_intent` accepts; Fase 13+ must keep both in sync).
- New phase → add its tests with the feature (operating rule 5), then run §1.

## 4. STOP policy (mandatory for small/cheap models)

This is not advice. A model running on a cost-saving tier MUST follow it:

1. Write the code, then run the gates in §1 order.
2. **Deterministic formatters may auto-fix**: `uv run ruff format`,
   `pnpm exec prettier --write`. They perform no reasoning; re-run the gate.
3. **Any other red gate (test failure, lint error, type error, build error) →
   STOP. Do not iterate. Do not "try one more thing".** Fix loops on a weak
   model burn more context and money than a single handoff to a capable model.
4. Emit a HANDOFF block (§6) as the last message of the session and end it.

Rationale: a red gate after formatter auto-fix means the change is wrong or
the model misunderstands the invariant. Both cases are fixed cheaper by a
stronger model with the error summary than by repeated guessing.

## 5. Explicitly NOT gated (and why)

- **mypy**: the project standardizes on **Pyright only**
  (IMPLEMENTATION_PLAN decision 20). Two type checkers produce conflicting,
  ambiguous failures that small models cannot triage. Do not add mypy.
- **Docker/container tests**: containerized deployment is explicitly deferred
  infrastructure. The equivalent gate is the smoke test: a real server process
  against an isolated data directory, no Docker required.
- **Real-browser tests**: deferred to Fase 16 by explicit user decision
  (`observations.md` checklist). Until then: jsdom component tests only.
- **Live-network tests**: opt-in (`LMD_LIVE_NETWORK=1`), never in CI or in the
  default gate run. The smoke test deliberately uses unresolvable `.invalid`
  URLs so it stays hermetic while still exercising real yt-dlp failure mapping.
- **Coverage thresholds**: signal over noise. The contract tests (§2) catch
  the drift that matters; a percentage target would only teach models to write
  filler assertions.

## 6. HANDOFF format (copy-paste on red)

```text
HANDOFF — <phase or task name>
Gate: <exact command that failed>
Status: <1-3 lines: what failed, file + line if known>
Evidence: <trimmed failing output, max ~30 lines>
Touched: <files changed this session>
Suspect: <where the fix probably lives, or "unknown">
Tried: <only formatter auto-fixes, or "nothing — stopped per §4">
```

## 7. Known gate pitfalls (read before debugging the harness)

- **Stale port (Regla 10.2)**: never interpret an e2e response without proving
  the listener is your process. The smoke test allocates a fresh port per run
  and proves ownership via the fresh install token — copy that pattern.
- **Infinite SSE over TestClient (Regla 6.1)**: consume the `_event_stream`
  generator directly, never via `client.stream()`. Over real HTTP, open the
  stream and assert headers only.
- **`response_model=None` (Regla 12.2)**: an endpoint returning `JSONResponse`
  in any branch must set `response_model=None`, or `create_app()` explodes at
  import and the whole suite fails to collect.
- **413 probe isolation**: the size guard answers before consuming the request
  body, so reusing that keep-alive connection poisons the next request. Probe
  oversized bodies with a fresh one-off client, last (`test_smoke_e2e.py`).
- **Scheduler pickup in contract tests**: the in-process scheduler dispatches
  QUEUED jobs within ~50 ms using the REAL executor. Any test that creates
  jobs over HTTP must inject a no-op `executor_factory`, or it performs real
  downloads and dedupe assertions go flaky (`test_contracts.py` pattern).
- **Svelte server build under Vitest**: component tests fail with
  `lifecycle_function_unavailable` unless `resolve.conditions: ['browser']` is
  set (`apps/web/vite.config.ts`). Do not remove it.
- **svelte-check covers `apps/web/tests/`** (via `tsconfig.app.json`
  `include`). Test files must typecheck under `strict`: no `any`, no unused
  locals in spirit — the same bar as `src/`.

## 8. Gate matrix for the remaining phases

| Phase | Gates that must stay green + new tests expected |
|---|---|
| 13 Media presets | `test_contracts.py` (intent shapes unchanged); `presets.test.ts` extended per preset; Resolve/Batch screens render the new preset list (component test) |
| 14 Advanced processing | planner + adapter tests per capability matrix (plan §528: "each feature needs a separate capability matrix and tests"); Zod schemas extended if DTOs grow |
| 15 Performance | gates unchanged; measurements live outside the suite (no perf assertions in CI — flaky by nature) |
| 16 Packaging | full gates + smoke on the **installed bundle** (PyInstaller onedir) + the real-browser checklist in `observations.md` (the moment jsdom stops being enough) |
| 17 Release hardening | full gates + smoke; reliability/security/UX items each get a regression test or an explicit `observations.md` entry explaining why not |
