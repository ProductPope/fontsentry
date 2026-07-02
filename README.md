# FontSentry

Audit and monitor the fonts used across many web domains, and estimate the
probability that each detected font is being used **in violation of its license**.

FontSentry crawls a configurable list of domains, detects every web font and how
it is embedded, downloads reachable font files to read their metadata, and scores
each font against an editable, rule-driven risk engine. It aggregates the same
font across all domains so cross-domain rules (e.g. "this license permits at most
N domains") can be evaluated globally. Findings already covered by a license
registry you maintain are suppressed automatically.

> [!IMPORTANT]
> **The risk score is a heuristic estimate, not legal advice.** A high score means
> "worth a human looking at the license", not "infringement". FontSentry does not
> determine legal liability. Always confirm with the owner or your legal team.

> [!TIP]
> **Not technical?** See [START_HERE.md](START_HERE.md) — set up and run the
> local app by pasting one prompt into Claude Code, then do everything in the
> browser (no CLI, no config files).

## Status

Early development. See [CHANGELOG.md](CHANGELOG.md) and the build phases in
[docs/methodology.md](docs/methodology.md).

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

The JavaScript-injected-font fallback renderer is optional and heavy:

```bash
uv sync --extra browser
uv run playwright install chromium
```

## Quickstart (demo dataset)

The `demo/` directory contains a self-contained, offline dataset (static pages,
crafted fonts, a matching registry). No internet or private data required:

```bash
# (wired up in a later phase)
uv run fontsentry scan --demo
```

## Local web UI

A local dashboard to run audits, browse findings, diff runs, and schedule recurring
audits. Everything runs on your machine — the server binds to `127.0.0.1` only.

```bash
# one-time: build the frontend (requires Node 20.19+)
cd web && npm install && npm run build && cd ..

# install the backend extra and launch
uv sync --extra web
uv run fontsentry serve        # → http://127.0.0.1:8000
```

- **Start audit** runs a scan (demo or real) and shows the report when it finishes.
- **Schedule recurring audit** creates a Windows Task Scheduler entry that runs
  `fontsentry scan` on a cadence — even when the UI is closed (Windows only).

Frontend dev mode (hot reload, proxies `/api` to the backend):

```bash
uv run fontsentry serve            # terminal 1
cd web && npm run dev              # terminal 2 → http://127.0.0.1:5173
```

See [web/DESIGN_SYSTEM.md](web/DESIGN_SYSTEM.md) for the UI design system.

## Configuration

All real user data lives **outside** the repo. Commit only the `*.example.yaml`
templates; copy them to their real (gitignored) names and edit:

| Example file | Real file (gitignored) | Purpose |
| --- | --- | --- |
| `config/targets.example.yaml` | `config/targets.yaml` | Domains to scan + subdomain seeds |
| `config/settings.example.yaml` | `config/settings.yaml` | Crawl depth, limits, rate, output paths |
| `config/rules.example.yaml` | `config/rules.yaml` | Risk-engine rules, weights, thresholds |
| `registry/licenses.example.yaml` | `registry/licenses.yaml` | Your owned-license registry |

License proof PDFs and invoices go in `registry/proofs/` and are never committed.

## CLI

```
fontsentry scan              crawl + detect + score + report
fontsentry report            re-render HTML from an existing JSON run
fontsentry diff              compare two runs
fontsentry registry validate check the registry file and proof paths
fontsentry rules validate    sanity-check the rule file
```

## Documentation

- [Risk rules reference](docs/rules.md) — scoring model and how to add a rule
- [Methodology](docs/methodology.md) — how this was built (vibecoding benchmark)
- [ADR 0001 — stack choice](docs/adr/0001-stack-choice.md)
- [ADR 0002 — risk-scoring model](docs/adr/0002-risk-scoring-model.md)
- [CLAUDE.md](CLAUDE.md) — working agreement and conventions

## License

[MIT](LICENSE)
