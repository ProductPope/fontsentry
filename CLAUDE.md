# CLAUDE.md — working agreement for FontSentry

Guidance for future Claude Code sessions working in this repo.

## What this project is

A CLI (and local web UI) that crawls web domains, detects fonts and their embedding
method, reads font metadata, and gives each font two deterministic verdicts — a
license verdict (`OK` / `NEEDS_CHECK` / `VIOLATION`, with a reason) and a privacy
verdict — via a fixed decision table (ADR 0003), plus an editable classification
config. The verdicts are an explicitly-labelled deterministic aid, never legal
advice.

## Architecture (strict separation of concerns)

```
src/fontsentry/
  config.py    load + validate YAML config (pydantic models in models.py)
  models.py    pydantic domain models (Finding, DetectedFont, RegistryEntry, ...)
  crawl/       async fetch, robots, passive discovery, on-disk cache
  detect/      html + css parsing, embedding classification, font-file metadata
  risk/        deterministic verdict engine (classify_license) + classification helpers
  registry/    owned-license registry + suppression logic
  report/      json (source of truth), html (jinja2), diff
  web/         FastAPI backend for the local UI (server, jobs, scheduler)
  cli.py       typer surface ONLY — no business logic lives here

web/           React + Vite + Tailwind frontend (separate Node toolchain)
```

The local UI (`fontsentry serve`, `web` extra) is a thin FastAPI layer over the
same pipeline: it lists/loads runs, starts scans, diffs, and manages recurring
audits via the OS scheduler (`web/scheduler.py`: Windows Task Scheduler on Windows,
cron on Linux; per-platform backends behind a dispatch, the API returns 501 on
other platforms such as macOS). The server binds 127.0.0.1 only and rejects cross-origin
state-changing requests. Frontend lives in `web/` with a token-based design system
(see `web/DESIGN_SYSTEM.md`); the built `web/dist` is served by the backend.

Data flows one way: **crawl → detect → classify (verdicts + registry) → report.**
Cross-domain facts need the full set of detected fonts, so aggregation happens
after the whole crawl completes, before classification.

## Conventions

- Python 3.12+, full type hints, `mypy --strict` clean.
- Functions and modules small and single-purpose. No business logic in `cli.py`.
- Inject "now" (a `datetime`) into anything time-dependent (expiry rules) so tests
  are deterministic. Never call `datetime.now()` deep in the logic.
- Pydantic v2 for every config and domain model. Validate at the edges.
- Brand-neutral: no real company names, logos, foundries, or internal references
  anywhere in code, docs, default config, or demo data. Use invented names.
  **One deliberate exception:** `registry/catalog.py` carries real, public
  open-source font family names (Roboto, Open Sans, …) — it's a functional
  autocomplete catalog for the registry form, not demo/marketing data. Don't
  "brand-neutralize" it.

## Run it

```bash
uv sync                       # install (add --extra browser for Playwright)
uv run pytest                 # tests (offline only — never hit the network)
uv run ruff check .           # lint
uv run ruff format .          # format
uv run mypy                   # types
```

## First-run bootstrap (non-technical user)

`START_HERE.md` tells a non-technical user to paste a "set up and run FontSentry
for me" prompt into Claude Code. When you get that request, do this in order and
keep every explanation plain — no jargon, no asking them to edit files or run
commands themselves:

1. Ensure prerequisites, installing any that are missing:
   - **uv** — https://docs.astral.sh/uv/ (Python 3.12+ toolchain)
   - **Node.js 18+ / npm** (only to build the web UI)
2. Install deps: `uv sync --extra web`
3. Build the UI: `cd web && npm install && npm run build`
4. Start the local app (binds 127.0.0.1 only): `uv run fontsentry serve`
   — it serves the built UI **and** the API at http://127.0.0.1:8000.
5. Open http://127.0.0.1:8000 in their browser.
6. Hand off to the UI in plain language: the Overview shows a 3-step
   **Getting started** — add websites (Targets), run an audit (**Start audit**;
   *demo* mode needs no real sites), read results (High/Medium/Low; open a row
   for the why + what-to-do).

All configuration and operation live in the UI (Targets, Registry, Rules,
scans, schedules). Do **not** route a normal user through YAML or the CLI.
Everything stays local — never send their domains or licenses anywhere.

## How to change classification (verdicts)

The engine is a fixed decision table (ADR 0003), not weighted rules. Tune *data* in
`config/rules.example.yaml` (open-license patterns, free owners, open/paid-tier
families, self-host-prohibited lists, paid CDNs, desktop formats, subset threshold);
the *mechanics* live in `risk/`.

1. To retune, edit the classification lists in `config/rules.example.yaml`.
2. For a genuinely new *kind* of check, add a helper in `risk/rules.py` and wire it
   into `classify_license` in `risk/engine.py` (data in YAML, mechanics in code).
3. Add a deterministic unit test in `tests/test_risk_engine.py` (known input →
   expected verdict; offline, no network).
4. Document it in `docs/rules.md`. Verdicts stay three-valued: OK / NEEDS_CHECK /
   VIOLATION.

## What must NEVER be committed

Real `config/*.yaml` (only `*.example.yaml`), `registry/licenses.yaml`, anything
under `registry/proofs/` (except `.gitkeep` and the one synthetic example),
generated reports, caches, workspace backups (`backups/`), any local-only
`external/` material, `.env`. Enforced by `.gitignore` **and** CI-guarded by
`tests/test_gitignore.py`, which fails if a sensitive path stops being ignored or
if real user data ever becomes tracked. Keep both tight.

## Testing rules

- Tests are 100% offline. Use local fixtures and `httpx.MockTransport`; never the
  live network. Playwright tests are marked `slow` and excluded from default CI.
- Mirror the package layout under `tests/`.
- **Frontend:** Vitest + React Testing Library, co-located `*.test.ts(x)` under
  `web/src`. `npm test` runs them; `npm run test:coverage` enforces a coverage
  **floor** on the pure-logic modules in `web/src/lib` (a ratchet — widen
  `coverage.include` in `vite.config.ts` as more modules get unit tests).
  Components are tested behaviourally (RTL), where line % is a weak metric.

## Docs stay current (enforced)

`tests/test_docs.py` is a CI-enforced freshness guard: it fails if a classification
config key or a `CrawlSettings` field is undocumented, or if `CHANGELOG.md` lost its
`[Unreleased]` section. So **update docs in the same PR as the code** — a new
classification key or setting without a doc entry turns CI red.
When you add a user-facing feature, also update the relevant doc (README CLI
options, `docs/rules.md`, `config/*.example.yaml` comments) and add a CHANGELOG
entry. Extend `test_docs.py` when a new kind of doc↔code contract is worth pinning.

The web UI has an **accessibility lint** (`cd web && npm run lint`,
`eslint-plugin-jsx-a11y` via `web/eslint.config.js`) that fails on WCAG
regressions. Run it before merging UI changes and wire it into the `web` CI job
(an `npm run lint` step before build). Keep it green; use a scoped
`eslint-disable-next-line` with a reason only for genuine false positives (e.g.
backdrop click-to-close).

## Commits

Conventional Commits. Small, logical commits. One coherent change per commit.
