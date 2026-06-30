# CLAUDE.md — working agreement for FontSentry

Guidance for future Claude Code sessions working in this repo.

## What this project is

A CLI that crawls web domains, detects fonts and their embedding method, reads
font metadata, and scores each font for license-violation risk against an editable
rule set. The risk score is an explicitly-labelled heuristic, never legal advice.

## Architecture (strict separation of concerns)

```
src/fontsentry/
  config.py    load + validate YAML config (pydantic models in models.py)
  models.py    pydantic domain models (Finding, DetectedFont, RegistryEntry, ...)
  crawl/       async fetch, robots, passive discovery, on-disk cache
  detect/      html + css parsing, embedding classification, font-file metadata
  risk/        data-driven scoring engine + rule loading
  registry/    owned-license registry + suppression logic
  report/      json (source of truth), html (jinja2), diff
  web/         FastAPI backend for the local UI (server, jobs, scheduler)
  cli.py       typer surface ONLY — no business logic lives here

web/           React + Vite + Tailwind frontend (separate Node toolchain)
```

The local UI (`fontsentry serve`, `web` extra) is a thin FastAPI layer over the
same pipeline: it lists/loads runs, starts scans, diffs, and manages recurring
audits via the Windows Task Scheduler (`web/scheduler.py`, Windows-only — the API
returns 501 elsewhere). The server binds 127.0.0.1 only and rejects cross-origin
state-changing requests. Frontend lives in `web/` with a token-based design system
(see `web/DESIGN_SYSTEM.md`); the built `web/dist` is served by the backend.

Data flows one way: **crawl → detect → risk (+ registry suppression) → report.**
Cross-domain rules need the full set of detected fonts, so aggregation happens
after the whole crawl completes, before scoring.

## Conventions

- Python 3.12+, full type hints, `mypy --strict` clean.
- Functions and modules small and single-purpose. No business logic in `cli.py`.
- Inject "now" (a `datetime`) into anything time-dependent (expiry rules) so tests
  are deterministic. Never call `datetime.now()` deep in the logic.
- Pydantic v2 for every config and domain model. Validate at the edges.
- Brand-neutral: no real company names, logos, foundries, or internal references
  anywhere in code, docs, default config, or demo data. Use invented names.

## Run it

```bash
uv sync                       # install (add --extra browser for Playwright)
uv run pytest                 # tests (offline only — never hit the network)
uv run ruff check .           # lint
uv run ruff format .          # format
uv run mypy                   # types
```

## How to add a risk rule

1. Add an entry to `config/rules.example.yaml` with `id`, `description`, `weight`,
   `confidence`, and its match condition. Document it with an inline comment.
2. If it needs a new condition type, implement the predicate in `risk/engine.py`
   and register it; keep rule *data* in YAML, rule *mechanics* in code.
3. Add a unit test in `tests/test_risk_engine.py` (use fixtures, no network).
4. Document the rule in `docs/rules.md`.

## What must NEVER be committed

Real `config/*.yaml` (only `*.example.yaml`), `registry/licenses.yaml`, anything
under `registry/proofs/` (except `.gitkeep` and the one synthetic example),
generated reports, caches, `.env`. Enforced by `.gitignore` — keep it tight.

## Testing rules

- Tests are 100% offline. Use local fixtures and `httpx.MockTransport`; never the
  live network. Playwright tests are marked `slow` and excluded from default CI.
- Mirror the package layout under `tests/`.

## Commits

Conventional Commits. Small, logical commits. One coherent change per commit.
