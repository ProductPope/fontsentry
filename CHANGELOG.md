# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Opt-in public-subdomain discovery** via Certificate Transparency: tick
  **Find subdomains** when starting a real audit to seed the crawl with public
  subdomains from crt.sh. Off by default and real-mode only — it queries an
  external service (the domain leaves the machine); it never brute-forces DNS.
- Each finding records **which pages the font was seen on** — a distinct page
  count plus a few sample URLs (`Finding.page_count` / `example_urls`), shown as
  "Seen on N pages, e.g. …" in the finding detail. Report schema bumped to **v5**
  (additive; pre-v5 reports still load).

### Changed
- Demo and example data are fully brand-neutral: real names (system fallback
  fonts, an open-font service) are replaced with invented ones in the demo
  dataset, `registry/licenses.example.yaml`, and the UI's "Insert examples" rows.
  The real-CDN embedding classifications (google_fonts / adobe_fonts / monotype)
  and CSS fallback stacks are unchanged — those are functional, not branding.

## [0.2.0] - 2026-07-02

### Changed
- **Breaking:** renamed the `foundry` field to `owner` throughout — domain models,
  report JSON (schema bumped to v3), the license registry YAML key, the risk-rule
  params (`foundries` → `owners`, `free_foundries` → `free_owners`), the CLI/HTML
  report columns, and the web UI. Existing `licenses.yaml` files and pre-v3 report
  JSON that use `foundry` must be updated to `owner`.

### Added
- **Redesigned local web UI** — a sidebar-navigated app (Overview, Audits,
  Registry, Targets, Rules) with dependency-free hash routing, a light/dark theme,
  self-hosted IBM Plex fonts (offline), and a token-based design system. Everything
  a non-technical user needs happens in the browser — no CLI or YAML editing; see
  `START_HERE.md` for the one-paste Claude Code setup prompt.
  - **Overview dashboard**: risk-posture cards (open findings per band + suppressed)
    with "vs last run" deltas, a portfolio card, an active-findings trend sparkline,
    and a "Changes since last run" panel.
  - **Rules** screen to edit rule weights/confidence and band thresholds, backed by
    `GET`/`PUT /api/config/rules`.
  - **Audits** screen: a run timeline (click to open a run) and schedule management.
  - **Registry** as license cards with an add/edit form and **proof-file upload**
    (`POST`/`GET /api/registry/proof`; extension-allowlisted, size-capped,
    traversal-safe).
  - **Targets** with per-domain reachability (from the latest run) and CSV import.
  - **Plain-language finding detail** — why it's flagged, what to do, and a
    score-breakdown gauge showing which rules fired.
  - **First-run onboarding** guiding add-websites → run → read results.
  - Responsive mobile drawer and a WCAG-AA contrast pass.
- **Changes since last run**: the Overview surfaces new / resolved / changed
  findings versus the previous run, backed by `GET /api/runs/{id}/diff` (reusing
  the existing `diff_runs`). A run with no earlier run returns an empty diff.
- **First seen** per (domain, font) in the Domains view, computed on demand from
  the run reports on disk (`GET /api/first-seen`) — no stored history.
- Per-host **asset paths**: each detected font now records the font-file URL(s) it
  was served from on each host (`DomainFont.assets`), surfaced as a **Source** column
  in the web UI's Domains view. Report JSON schema bumped to **v4** — additive, so
  pre-v4 reports still load (the field defaults to empty).
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

[Unreleased]: https://github.com/fontsentry/fontsentry/compare/v0.2.0...main
[0.2.0]: https://github.com/fontsentry/fontsentry/releases/tag/v0.2.0
