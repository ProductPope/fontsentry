# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Detection gaps found against a ground-truth test page** (fontsentry.com/poligon):
  read OS/2 `fsType` and flag a self-hosted font whose Restricted-License bit
  forbids embedding as a **VIOLATION**; **follow CSS `@import`** so fonts delivered
  through an imported sheet are detected (not seen only as a usage); and classify a
  family referenced with no `@font-face` and not on the known-system list as
  **UNKNOWN delivery** (→ needs-check with an evidence note) instead of a clean
  system font — closing false "OK / system" results for JavaScript-injected fonts.

### Changed (breaking)
- **Deterministic verdicts replace the weighted risk score** (ADR 0003). Each font
  now carries a **license verdict** (`OK` / `NEEDS_CHECK` / `VIOLATION`) with an
  explicit reason and evidence notes, plus the existing **privacy verdict**. The
  score/band and `triggered_rules` are gone; the engine is a fixed decision table.
  `rules.yaml` becomes classification data (no `scoring:`/weights) — a breaking
  config change; report schema bumped to 9 (older reports still load). JSON/HTML/CSV
  reports, the run diff, the CLI, and the web UI all move to verdicts.

### Added
- **Detection-accuracy validation** (`tests/test_detection_accuracy.py`): measures
  embedded-font detection as precision/recall against the demo corpus's known
  ground truth (100%/100% — no false families, none missed), documented in
  `docs/methodology.md` with a path to external validation on hand-verified pages.
- **Performance characterisation** in `docs/methodology.md` (CPU ceiling,
  politeness-bound throughput, bounded memory) plus a real-DNS verification of the
  SSRF guard — concrete answers to "how does it scale / is it safe?".
- **Detection-accuracy guards**: a regression test pins that messy CSS (`font:`
  shorthand, `var()`, generics) yields only real families; an end-to-end test
  confirms a non-UTF-8 (latin-1) page's font family decodes correctly.

### Changed
- **Refactor: slim `web/server.py`** (485 → 368 LOC) by moving non-glue code out of
  the HTTP layer: response models → `web/schemas.py`, the scan-job orchestration →
  `web/scan_job.py`, path helpers → `web/paths.py`. Behaviour-preserving (the API
  tests pass unchanged); `server.py` is now a thin FastAPI layer.
- **Refactor: split the FindingsTable god-component** (603 → 357 LOC). Pure logic
  moved to `lib/findings.ts` (unit-tested, 100%); the detail panel to
  `features/finding-detail.tsx`. Behaviour-preserving — the Phase-2 behavioural
  tests pass unchanged.

### Added
- **Frontend test suite (Vitest + React Testing Library)**: behavioural tests for
  the findings table (variant grouping, "needs action" filter, sort/expand, a11y
  labels) and unit tests for the `web/src/lib` logic, with a CI-enforced coverage
  floor on the pure-logic modules. `npm test` / `npm run test:coverage`.
- `SECURITY.md` (private reporting + threat model) and GitHub issue templates.

### Fixed
- **Correct package/crawler URLs**: the placeholder `github.com/fontsentry/fontsentry`
  (package metadata + crawler User-Agent) now points at the real repository.
- **Accessibility: navigation & structure** — a "Skip to content" link bypasses the
  sidebar (2.4.1); content sections carry headings so the outline has no gaps
  (1.3.1/2.4.6); the mobile navigation drawer moves focus in on open and closes on
  Escape (2.1.1/2.4.3).
- **Accessibility: forms, toggles, and error messages** — the Targets textarea has
  a programmatic label (1.3.1); the add-license form shows an inline, field-associated
  error with `aria-required`/`aria-invalid` instead of a toast only (3.3.1/3.3.3);
  segmented single-select toggles are wrapped in `role="group"` with a label
  (1.3.1/4.1.2); error toasts use `role="alert"`/`aria-live="assertive"` and no
  longer auto-dismiss (2.2.1/4.1.3).
- **Accessibility: findings table (WCAG 1.4.1 / 4.1.2)** — the Delivery badge now
  carries a screen-reader text label (not colour + `⚠` glyph alone); the sortable
  Score header exposes `aria-sort`; expandable rows link to their detail via
  `aria-controls` and hide the `▸/▾` glyphs from the accessible name.
- **Accessibility: text contrast (WCAG 1.4.3)** — darkened the `faint` metadata
  text token in both themes and the HTML report's low/medium risk badges so small
  text clears the 4.5:1 AA threshold.

### Added
- **Accessibility lint** (`npm run lint`, `eslint-plugin-jsx-a11y` via
  `web/eslint.config.js`): fails on WCAG regressions in the React UI. Wire it into
  the `web` CI job (an `npm run lint` step) to enforce it on every PR.
- **Documentation-freshness guard** (`tests/test_docs.py`): CI now fails if a rule
  predicate, a default rule id, or a `CrawlSettings` field is undocumented, or if
  the CHANGELOG loses its `[Unreleased]` section — keeping the repo docs in lockstep
  with the code.

### Changed
- **Test suite deepened to benchmark grade** (168 → 255 tests): direct coverage
  for `detect/page`, per-predicate rule edge cases, registry suppression
  boundaries, config save/load round-trips, robots crawl-delay + allow-by-default,
  CT-log response shapes, sitemap-index, charset decode, and SSRF/size-cap paths.

### Fixed
- **Old reports survive tool upgrades**: report models now ignore unknown fields
  (forward/back-compatible), so a report written by a different schema version
  still loads instead of silently vanishing from the run list. Config files stay
  strict (typos still rejected), and unreadable reports are now logged when
  skipped rather than dropped silently.

### Added
- **CLI ↔ API parity**: `fontsentry scan` gains `--discover-subdomains`,
  `--max-pages`, and `--csv` (write a findings CSV alongside the JSON/HTML),
  matching what the web API already offered.
- **Sitemap-index support**: a `<sitemapindex>` is now recursed one level (up to
  20 child sitemaps) so page discovery works on large sites that split their
  sitemap, instead of silently finding nothing.

### Fixed
- **Charset-aware decoding**: fetched HTML/CSS is decoded using the
  `Content-Type` charset (then UTF-8), so a legacy latin-1 / Shift-JIS page no
  longer yields mojibake family names that break registry matching.
- **Redirected responses aren't mis-cached**: a body reached via a redirect is no
  longer stored under the original URL (which could later serve the wrong content).
- **Risk scoring closes three false-negative gaps** (a real violation could be
  silently under-scored):
  - Fonts are aggregated by **(family, owner)**, so a benign/free owner on one
    page can no longer mask a commercial owner of the same family on another.
  - A rule can be marked **`hard: true`** (expired/over-limit license, prohibited
    self-hosting, paid tier); such findings are **not** score-halved when the font
    is served-but-not-applied.
  - An **expired or non-covering** registry entry no longer grants safe harbor —
    the commercial/paid-CDN signals still fire (coverage now means a *valid*
    license, not merely that an entry exists).

### Added
- **SSRF guard for the crawler**: font/CSS/redirect/CT URLs that resolve to
  loopback/private/link-local/reserved addresses are refused (redirects are now
  followed manually and checked per hop). On by default; set
  `crawl.block_private_hosts: false` to audit internal/staging sites.
- **Response-size cap**: fetched bodies are streamed and aborted past
  `crawl.max_response_bytes` (default 25 MB), bounding decompressed size too — a
  decompression bomb or huge asset can no longer OOM a scan. The real-scan HTTP
  client now also has finite timeouts and a connection limit.
- **Concurrent page detection**: the detect pass fans out (bounded by the
  existing per-run concurrency + per-host throttle), so `crawl.concurrency`
  finally speeds up large scans instead of being a no-op.

### Fixed
- **Subdomains are covered by their parent domain's license**: a license for
  `example.com` now covers `www.example.com` (dot-bounded), and `max_domains`
  counts distinct licensed domains (apex + subdomains under one license = one),
  so real, valid licenses stop showing as open findings.
- **CSV export is safe to open in a spreadsheet**: cells starting with
  `= + - @` (from attacker-influenceable font metadata/URLs) are neutralized,
  preventing CSV formula/DDE injection.
- **Proof upload is streamed with a hard cap**: the 10 MB limit aborts mid-read
  instead of buffering the whole (possibly length-lying) body first.
- **`run_id` path handling is resolve-and-contain**: report ids are resolved and
  verified to sit inside the reports dir (blocks absolute/encoded/drive escapes),
  matching the proof-serve defense.
- **Misspelled rule field names no longer fire spuriously**: `missing_name_field`
  ignores unknown field names instead of treating them as "missing".
- Report file globs are unified to `fontsentry-*.report.json` across all endpoints.
- **A malformed font no longer aborts the whole scan**: font-table decompilation
  errors (corrupt name/maxp) are caught and surfaced as `FontReadError` instead
  of crashing the crawl.
- **Look-alike hosts are no longer treated as same-site**: `_same_site` now
  requires an exact host or dot-bounded subdomain, so `notexample.com` on
  `example.com` is correctly classified third-party (its privacy signal is kept).
- **`font` shorthand parsed correctly**: the family list is taken from after the
  size token, so `font: bold 12px/1.5 "Demo Sans"` records `Demo Sans` instead of
  a garbage `bold 12px/1.5 …` family (removes spurious system findings).
- **Scan jobs fail loudly**: a bad config now marks the job `error` instead of
  leaving it stuck `running` (and no longer leaks the HTTP client).
- **CSRF hardening**: state-changing requests with `Sec-Fetch-Site: cross-site`
  are rejected even when the `Origin` header is absent.
- **Crawled URLs are only linked when `http(s)`**: font-file / page URLs from
  audited sites render as plain text if they use a `javascript:`/`data:` scheme.

### Added
- **Font-variant grouping**: weight/style variants of one family (`metropolis`,
  `metropolis-bold`, `OpenSans-Regular`, …) now fold into a base family
  (`Finding.family_group`; report schema **v8**; new CSV `family_group` column).
  The Fonts table groups them under one expandable row (worst band + variant
  count), with a **Group variants** toggle. Width (Condensed/Narrow) stays
  distinct.
- **Registry autocomplete**: the add-license form suggests font families from
  the fonts detected in your latest audit plus a bundled catalog of common
  open-source families (available before the first audit), and auto-fills the
  owner when you pick a known family — fewer typos. New `GET /api/known-fonts`.
- **UI re-attaches to a running audit**: on load the app checks `GET /api/jobs`
  for an in-flight scan (started from the CLI, another tab, or a prior session)
  and shows its live progress — the progress bar is no longer limited to scans
  started from the button. Jobs now record their `mode` so the view lands on the
  right data set when the scan finishes.

### Fixed
- **CSS-escaped family names no longer duplicate a font**: an unquoted
  `font-family` with backslash-escaped spaces (e.g. `Font Awesome\ 5 Free`) is
  now unescaped to match its quoted form, so the same font isn't counted twice.

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

[Unreleased]: https://github.com/ProductPope/fontsentry/compare/v0.2.0...main
[0.2.0]: https://github.com/ProductPope/fontsentry/releases/tag/v0.2.0
