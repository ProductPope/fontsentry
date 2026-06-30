# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- CI (`ci.yml`) running ruff, mypy, and pytest; scheduled monitoring (`monitor.yml`)
  reading private targets/registry from secrets.

[Unreleased]: https://github.com/fontsentry/fontsentry/commits/main
