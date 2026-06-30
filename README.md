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
> determine legal liability. Always confirm with the foundry or your legal team.

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

## License

[MIT](LICENSE)
