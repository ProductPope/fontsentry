# Methodology: a vibecoding benchmark

FontSentry was built as a public benchmark of what can be produced with Claude
Code when both the **artifact** (a working tool) and the **process** (clean
commits, tests, CI, docs, decision records) are treated as deliverables of equal
weight. This document records how it was produced so the process is reproducible
and auditable.

## Approach

The work was specified once, up front, as a detailed brief, then implemented in
discrete phases. Each phase had verifiable success criteria and ended in a single
Conventional-Commit. The full quality gate — `ruff`, `ruff format`, `mypy --strict`,
`pytest` — was run and made green before every commit, so the history is bisectable
and every commit is a working state.

Two ground rules shaped the code:

- **Offline-first.** Detection and scoring were built and tested before the network
  crawler, and the entire test suite runs with no network access (httpx
  `MockTransport`, an in-memory font factory, and a filesystem-backed transport for
  the demo). Tests never touch live hosts.
- **Brand neutrality.** No real company, product, or foundry names appear anywhere
  in the code, docs, default config, or demo data. All such names are invented.

## Build phases

| Phase | Deliverable | Commit type |
| --- | --- | --- |
| 0 | Scaffold: uv, pyproject, ruff/mypy/pytest, CI, baseline docs | `chore` |
| 1 | Config + pydantic domain models, example YAML templates | `feat(config)` |
| 2 | Offline detection: HTML, CSS, embedding, font-file metadata | `feat(detect)` |
| 3 | Rule-driven risk engine + registry suppression | `feat(risk)` |
| 4 | Async crawler: fetcher, robots, passive discovery, cache | `feat(crawl)` |
| 5 | Reports: JSON source of truth, HTML dashboard, run diff | `feat(report)` |
| 6 | CLI, scan orchestration, offline demo dataset | `feat(cli)` |
| 7 | Docs, ADRs, methodology, monitor workflow | `docs` / `ci` |

## Architecture in one line

`crawl → detect → risk (+ registry suppression) → report`, with aggregation across
the whole crawl before scoring so cross-domain rules can be evaluated. Concerns are
strictly separated and the CLI holds no business logic. See the ADRs in
[`docs/adr/`](adr/) for the stack and scoring-model decisions.

## What "done" means here

- mypy-clean, ruff-clean, all tests passing, offline.
- One command (`uv run fontsentry scan --demo`) yields a meaningful report on a
  clean clone with no internet and no private data.
- The risk score is consistently framed as a heuristic estimate, never legal advice.
