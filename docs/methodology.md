# Methodology: vibecoding real problem solution

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

`crawl → detect → classify (verdicts + registry) → report`, with aggregation across
the whole crawl before classification so cross-domain facts can be evaluated.
Concerns are strictly separated and the CLI holds no business logic. See the ADRs
in [`docs/adr/`](adr/) — notably **ADR 0003**, which retired the weighted risk
score for **deterministic license + privacy verdicts** (a fixed decision table,
each verdict carrying an explicit reason).

## Detection accuracy

Detection (which web fonts a site serves) is the tool's proven, load-bearing
value — audits have surfaced fonts owners didn't know were deployed. It is
validated as **precision / recall** against a controlled ground truth:

- **Demo corpus** (synthetic fixtures with known fonts, `tests/test_detection_accuracy.py`):
  the five embedded `@font-face` fonts are detected with **100% precision and
  100% recall** — no false families (the `font:`-shorthand / `var()` / generic
  noise is filtered) and none missed; fallback families are correctly classified
  as *system*, not embedded. This runs offline and is reproducible via
  `uv run pytest tests/test_detection_accuracy.py`.
- **External validation** (recommended before publishing hard numbers): hand-verify
  the fonts on a handful of real pages (view-source / DevTools) and extend the
  ground-truth set. Report precision/recall on that set; state where it errs.

This is separate from the *verdict* layer — detection accuracy answers "did we
find the fonts?", not "is the licence/privacy call right?" (see ADR 0003).

## Performance characteristics

The crawler is **politeness-bound, not CPU-bound.** Numbers to set expectations
(not a tuned benchmark):

- **CPU ceiling** (offline, no network): the demo scan detects ~20 pages/second on
  a laptop — HTML/CSS/font parsing is not the bottleneck.
- **Real-world throughput** is governed by `crawl.per_host_rate_limit` (default
  2 req/s per host) and `crawl.concurrency` (default 8). A 25-host / ~100-page
  crawl completes in roughly ten minutes at defaults; raising `--max-pages` or the
  rate limit trades politeness for speed.
- **Memory is bounded**, not open-ended: each fetched body is streamed and capped
  at `crawl.max_response_bytes` (default 25 MB), so worst-case in-flight memory is
  ≈ `max_response_bytes × concurrency` (~200 MB), regardless of what a site serves.
- **SSRF guard** was verified against real DNS resolution: public hostnames resolve
  and pass; `localhost`, link-local (`169.254.169.254`), and private ranges are
  refused (`crawl.block_private_hosts`, default on).

## Hardening, then a judgement-layer change

After the initial build the project ran a **hardening roadmap** (see
[`docs/roadmap.md`](roadmap.md)): frontend test net + coverage floor, god-file
refactors, a crawler-reality/threat-model pass, and detection-accuracy validation —
each a small, evidence-producing phase, the judgement layer held frozen throughout.
Then, in exactly one phase, the judgement layer changed: **ADR 0003** replaced the
unvalidated weighted score with the deterministic verdict engine. Isolating that
change kept the infrastructure work and the later validation each pointed at a
stable target.

## Human review found real bugs

The process deliberately includes a **human check** — a person, not another AI
session. Running the finished tool against a purpose-built, labelled test page
(one font-delivery method per section) surfaced three genuine detection bugs that
the offline suite could not have caught on its own:

1. fonts delivered via CSS `@import` were seen only as usages and misread as system
   fonts;
2. JavaScript-injected fonts were reported as a clean "OK / system";
3. a font whose OS/2 `fsType` forbids embedding was not flagged.

Each was fixed in its own commit **with a regression test**. The same check also
found two cases that were *deliberately not* pursued — flagging the common
Preview & Print `fsType` bit (would manufacture false positives) and full
JavaScript rendering (a heavy, optional Playwright subsystem). Those are recorded
as conscious non-goals in [`LIMITATIONS.md`](../LIMITATIONS.md). Documenting the
boundary is treated as a result, not a gap.

## Verdict validation (Phase 8)

Detection answers "did we find the fonts?"; this answers "is the **licence call**
right?" The verdict engine was checked against an **independent, human-labelled
ground truth** — the fonts of a real production web estate, labelled from each
font file's own producer and embedded licence string (i.e. judged from the
licensing facts, not from the tool's output). The labelled set and per-font results
are kept private; only the aggregate is reported here.

Set: **30 labelled fonts** across a spread of real sites.

| Outcome | Count |
| --- | --- |
| Detected & judged | **26** — agreement **88%** |
| Matched | 23 |
| Mismatched | 3 — **false-negatives (unsafe): 0** |
| Not detected | 4 |

What the numbers mean:

- **The denominators, stated plainly:** 88% is agreement over the **detected set**
  (23 of 26). Counted over **all 30 labels** — detection misses included —
  agreement is 23/30 = **77%**. Both are given so neither denominator is hidden.
- **Zero false negatives.** The tool never cleared a commercial / licence-unverified
  font as `OK`. Every commercial family in the set (self-hosted, no readable
  open-licence, not in the registry) was correctly returned as `NEEDS_CHECK`.
- **All 3 disagreements are the *safe* direction.** They are open families (Open
  Font Licence / Ubuntu Font Licence) the tool marked `NEEDS_CHECK` rather than
  `OK`, because the font file shipped no machine-readable open-licence string and
  the family was not in the open-family list. Over-caution is the *intended* failure
  mode: a `NEEDS_CHECK` is a prompt to verify, never a false clear.
- **The 4 "not detected" are a detection-recall matter, not a wrong verdict** — a
  font that lived only on a page the crawl didn't reach. Recall is measured
  separately (see *Detection accuracy*); it is not counted against the verdict
  rules.

Reproducible via the in-repo harness (`fontsentry validate --labels <file>`), which
runs real scans and compares them to the labels, exiting non-zero on any false
negative. The comparison logic is offline unit-tested; the ground-truth labels are
private, so the published figure is the aggregate above rather than a runnable
public corpus. It is a modest set: it confirms the *direction* of the rules (safe,
no false clears) more than it fixes a precise agreement rate.

One honest caveat about the ground truth itself: the labels were judged largely
from each font file's producer and embedded licence string — **the same
name-table fields the verdict engine reads** — so for the agreeing cases the
human is not a fully independent oracle, and the agreement rate partly measures
parser fidelity rather than rule correctness. The genuinely independent signal
is the *disagreements* (where the human used knowledge the file didn't carry —
all safe-direction here) and the zero-false-negative direction. A fully
independent label source would be foundry records or the actual EULAs, not the
files.

## What "done" means here

- mypy-clean, ruff-clean, all tests passing, offline.
- One command (`uv run fontsentry scan --demo`) yields a meaningful report on a
  clean clone with no internet and no private data.
- The verdicts are consistently framed as a **deterministic aid, not legal advice**;
  `NEEDS_CHECK` is owned as the honest default, and the limits are stated in
  [`LIMITATIONS.md`](../LIMITATIONS.md).
