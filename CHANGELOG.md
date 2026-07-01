# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Breaking:** renamed the `foundry` field to `owner` throughout — domain models,
  report JSON (schema bumped to v3), the license registry YAML key, the risk-rule
  params (`foundries` → `owners`, `free_foundries` → `free_owners`), the CLI/HTML
  report columns, and the web UI. Existing `licenses.yaml` files and pre-v3 report
  JSON that use `foundry` must be updated to `owner`.

### Added
- Web UI **Setup** section (collapsible, open on first visit): edit the domains to
  scan and the owned-license registry — including how each license may be used
  (allowed domains, max domains, validity) — directly from the dashboard. Backed
  by `GET`/`PUT /api/config/targets` and `/api/config/registry`, which read and
  write the local, gitignored `config/targets.yaml` and `registry/licenses.yaml`.
  The license table has per-header tooltips, license-type suggestions, and an
  "Insert examples" action that seeds illustrative rows.
- License registry `allowed_domains` now accepts the `"*"` wildcard, meaning the
  license is valid on any domain (unlimited scope).
- Project scaffold: `pyproject.toml` (uv, ruff, mypy, pytest), source layout,
  packaging metadata, MIT license, and baseline docs.
- Configuration system: pydantic v2 models and YAML loaders for settings, targets,
  rules, and the license registry, with committed `*.example.yaml` templates.
- Offline font detection: HTML and CSS parsing, embedding-method classification
  (self-hosted / Google / Adobe / Monotype / other CDN / system), font-format
  detection, and `name`-table metadata reading via fonttools.
- Rule-driven risk engine: editable predicates and weights from `rules.yaml`,
  cross-domain aggregation, normalized 0–100 scoring with low/medium/high bands.
- License registry with suppression (RESOLVED when a valid license covers a font).
- Async crawler: bounded-concurrency fetcher, per-host rate limiting, robots.txt
  support, passive page/subdomain discovery, and an on-disk conditional cache.
- Reporting: timestamped JSON source of truth, an accessible HTML dashboard, and a
  run-to-run diff over open findings.
- Typer CLI: `scan` (with `--demo`), `report`, `diff`, `registry validate`,
  `rules validate`.
- Offline demo dataset under `demo/` served via a filesystem transport.
- Documentation: README, `CLAUDE.md`, ADRs, rules reference, and methodology.
- CI (`ci.yml`) running ruff, mypy, pytest, and the web build; scheduled monitoring
  (`monitor.yml`) reading private targets/registry from secrets.
- Local web UI (`web` extra, `fontsentry serve`): a FastAPI backend (list/load runs,
  start scans, diff, manage schedules; localhost-only with Origin checks) and a
  React + Vite + Tailwind dashboard with a token-based design system and WCAG
  baseline. "Start audit" runs scans; "Schedule recurring audit" creates Windows
  Task Scheduler entries that run even when the UI is closed.

[Unreleased]: https://github.com/fontsentry/fontsentry/commits/main
