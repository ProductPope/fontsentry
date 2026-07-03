# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Privacy (GDPR/RODO) axis, independent of the license band**: every finding is
  now classified by delivery — `self_hosted`, `third_party_api`, `mixed`, or
  `not_applicable` (`Finding.privacy`; report schema **v7**; new CSV `privacy`
  column). Third-party delivery (e.g. the Google Fonts API) sends visitor IPs
  off-site — a GDPR concern even for a freely-licensed font. The Fonts table
  shows a **Delivery** badge and, per row, a self-hosting recommendation; Overview
  shows a privacy advisory banner when any font is third-party-served.
- **"Ignore free licenses" by default**: the Fonts table defaults to a **Needs
  action** filter (open license concerns + privacy flags) and hides open-licensed
  / low-risk fonts, with **Privacy (GDPR)** and **All** filters alongside.
- **Open icon fonts no longer false-positive; paid tiers flagged**: a new
  `open_families` param on `commercial_unregistered` recognizes openly-licensed
  families that ship without a license string (e.g. Font Awesome Free/Brands are
  OFL) by name, so they drop to LOW instead of MEDIUM. A new `family_name_matches`
  condition powers a `paid-tier-in-name` rule that flags paid tiers announced in
  the family name (e.g. Font Awesome **Pro**). `excludes` on the allowlist keeps
  paid tiers out of the open-family whitelist.
- **Demo runs are isolated from real data**: demo audits now write to
  `reports/demo/` and never appear under "Your data". Overview has a **Your data
  / Demo data** toggle; the run-list, run, diff, CSV, and first-seen endpoints
  take a `source` query param (`real` default, `demo`).
- **Run-audit modal**: Start audit now opens a modal to choose the data source
  (Your data / Demo data), toggle **Check subdomains**, set **max pages per
  domain**, and see an **estimated completion time** (from past audits'
  throughput, recomputed as the settings change).
- **Per-scan page cap**: `POST /api/scan` accepts `max_pages_per_domain` to
  override the per-host page limit for a single audit.
- **Scan-time estimate**: `GET /api/scan/estimate?hosts=&max_pages=` returns an
  ETA from recent runs' throughput (each run now records `duration_seconds`;
  report schema **v6**). Returns `null` until there's a timed run to learn from.
- **CSV export** of a run's findings — `GET /api/runs/{id}/export.csv` and an
  **Export CSV** button on Overview. One row per font (family, owner, band,
  score, status, applied, domain/page counts, domains, embeddings, formats,
  rules, example URLs, suppression reason).
- **Opt-in public-subdomain discovery** via Certificate Transparency: tick
  **Find subdomains** when starting a real audit to seed the crawl with public
  subdomains from crt.sh. Off by default and real-mode only — it queries an
  external service (the domain leaves the machine); it never brute-forces DNS.
- Each finding records **which pages the font was seen on** — a distinct page
  count plus a few sample URLs (`Finding.page_count` / `example_urls`), shown as
  "Seen on N pages, e.g. …" in the finding detail. Report schema bumped to **v5**
  (additive; pre-v5 reports still load).

### Changed
- Opt-in CT subdomain discovery now crawls each discovered subdomain as its
  **own host** — its own page budget and its own domain report — instead of
  folding them into the apex domain's budget.
- Fonts served via `@font-face` but **not applied to any text** (declared but
  never referenced by a `font-family` usage) are now flagged as such and scored
  lower (halved), so an unused hosted font no longer overstates its risk. The
  finding still appears — hosting the file can itself be a licensing concern.
- Font-family detection ignores CSS custom-property references
  (`var(--…)`) — these are variable lookups, not real families, and were
  surfacing as noise findings (e.g. `var(--bs-body-font-family)`).
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
