# 1. Technology stack

- Status: Accepted
- Date: 2026-06-30

## Context

FontSentry crawls several hundred domains, downloads and parses fonts, scores
license risk, and runs on a schedule in CI. It needs an async HTTP stack, robust
HTML/CSS parsing, font-binary introspection, validated config, a clean CLI, and a
tooling baseline (lint, types, tests) befitting a reference-quality codebase.

## Decision

Python 3.12+, managed with **uv**. Core libraries:

- **httpx** (async) for fetching, with bounded concurrency and per-host rate limits.
- **protego** for robots.txt (httpx has no parser; chosen over stdlib
  `urllib.robotparser` for crawl-delay support and Scrapy-grade correctness).
- **selectolax** for HTML parsing (fast, prebuilt wheels, low type friction) and
  **tinycss2** for structural CSS parsing instead of regexes.
- **fonttools** (+ **brotli**) to read the `name` table and detect format; brotli
  is required to decode woff2, the dominant web format.
- **pydantic v2** for config and domain models with validation at the edges.
- **typer** + **rich** for the CLI and terminal output.
- **jinja2** for the HTML report (autoescaped — name-table strings are untrusted).
- **pyyaml** for config and registry files.
- **playwright** as an *optional* extra, off by default, for the rare pages that
  inject fonts via JavaScript.

Quality tooling: **ruff** (lint + format), **mypy --strict**, **pytest**
(offline-only), all enforced in GitHub Actions.

## Consequences

- One dependency manager (uv) handles Python, venv, and locking reproducibly.
- Two additions beyond the original brief — `protego` and `brotli` — were
  necessary blockers (robots parsing; reading woff2) and are documented here.
- selectolax and fonttools ship partial/no type stubs; we scope
  `ignore_missing_imports` to those modules rather than relaxing strictness globally.
- Playwright stays optional so CI and a default install remain lightweight.
