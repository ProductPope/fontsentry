# Contributing to FontSentry

Thanks for your interest. This project doubles as a reference-quality open-source
codebase, so the bar for clean commits, tests, and docs is part of the point.

## Development setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```

## Before you open a PR

Run the full local check (CI runs the same):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

All four must pass. CI runs them on Python 3.12 and 3.13.

If you changed the web UI (`web/`), also run what the `web` CI job runs:

```bash
cd web
npm run lint            # accessibility lint (jsx-a11y)
npm run test:coverage   # unit tests + coverage floor
npm run build           # type check + production build
```

If you changed an API model or endpoint (`src/fontsentry/web/`, or a model it
returns), regenerate the contract and the UI types — never edit them by hand:

```bash
uv run python -m fontsentry.web.openapi > web/openapi.json
cd web && npm run gen:api   # → src/lib/api-schema.d.ts
```

`tests/test_openapi.py` and the `web` CI job fail if either is stale.

Dependency updates arrive as grouped weekly Dependabot PRs (Python, npm,
GitHub Actions).

## Conventions

- **Conventional Commits** for every commit, e.g. `feat(risk): add expiry rule`,
  `fix(crawl): handle redirect loops`, `docs: ...`, `test: ...`, `chore: ...`.
- Small, logical commits — one coherent change each.
- Full type hints; `mypy --strict` must stay clean.
- Keep concerns separated (crawl / detect / risk / registry / report). No business
  logic in the CLI layer.
- Tests are offline-only. Use fixtures and `httpx.MockTransport`; never hit the
  live network in a test.

## Brand neutrality (hard rule)

No real company names, logos, foundry names, product references, or internal data
anywhere — code, docs, default config, or demo dataset. Use invented names.

## Adding a risk rule

See the "How to add a risk rule" section in [CLAUDE.md](CLAUDE.md).

## Reporting issues

Open a GitHub issue. For anything that looks like a security concern, please note
it explicitly in the report.
