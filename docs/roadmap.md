# Hardening roadmap

Living plan (2026-07-04). Goal: bring FontSentry to a state that withstands a
CTO-level review and stands up as a conference benchmark — where the exhibit is
the *process and its evidence*, built with Claude Code.

The bar is **not** "nothing to criticise" (unachievable, invites gold-plating).
The bar is: **every decision is deliberate, documented, and defensible, and the
tool is honest about what it is and isn't.** A defended tradeoff is a passed
review; the failure mode is an *unforced error* or an *undefended claim*.

## Post-freeze detection work (2026-07-05)

After the `v0.4.0` freeze, two detection features closed the biggest recall gap
(self-hosted fonts on client-rendered SPAs): `scan-source` (audit font files in a
local repo, offline) and a live-scan **JS bundle scan**. Headless-browser
rendering ("B2") is **deliberately deferred** — the bundle scan covers the common
case and a browser is a heavyweight, less-deterministic dependency. Decision +
residue documented in [ADR 0004](adr/0004-spa-font-discovery.md).

## Current position (2026-07-04)

Phases **1–5 complete** (PRs #59–#64): hygiene, frontend test net + coverage floor,
god-file refactors, crawler-reality/perf/threat-model, and detection accuracy
(100%/100% precision-recall on the demo corpus). All gates green; 263 backend +
25 frontend tests. **Next: Phase 6** — deterministic verdicts (ADR 0003), the one
core/judgement-layer change; start it fresh, semantics first, then a focused PR,
then the Phase-7 human-review gate.

## What is already proven vs unproven

- **Detection (proven):** the crawl → detect → aggregate pipeline surfaces web
  fonts and their delivery method — audits have already revealed fonts the owner
  did not know were served. This is the tool's load-bearing, verifiable value.
  Lead with it. It still needs its *accuracy* measured (Phase 5).
- **Judgement layer (deterministic, rules to be validated):** per ADR 0003 the
  weighted risk score is retired for deterministic verdicts (privacy + licence,
  `UNKNOWN` first-class). Defensible by construction; the *rules* still get
  validated (Phase 8).

## Guardrails (hold for the whole roadmap)

- **The judgement layer changes in exactly one phase (Phase 6).** It is frozen
  before and after, so infrastructure work (Phases 1–5) and validation (Phase 8)
  each have a stable target. Never mix an infra change with a verdict change.
- **No new features. No abstractions on spec.** Rigour comes from evidence and
  honesty, not more code. Over-engineering is itself a review finding.
- **Offline-deterministic tests stay the default;** anything touching the live
  network is opt-in and out of default CI.

## Already at benchmark grade (do not redo)

MIT `LICENSE`, `CONTRIBUTING.md`, ADRs, `methodology.md`, committed lockfiles, CI
with guards (docs freshness, jsx-a11y, ruff/mypy/pytest), security hardening
(SSRF guard, response-size cap, CSV-injection, path containment), accessibility.

## Phases (execute in order)

### 1 — Hygiene & OSS completeness  · S · risk: none  · ✅ DONE (PR #59)
Fix `pyproject.toml` URLs; strengthen/remove tautological assertions; grep dead
placeholders; add `SECURITY.md`, `.github/ISSUE_TEMPLATE/`.
**Done:** correct package metadata; standard OSS meta-file set; no dead links.

### 2 — Frontend test net + coverage floor  · M · risk: low  · ✅ DONE (PR #60)
Vitest + RTL + jsdom, `npm test` in the `web` CI gate; behavioural tests for
FindingsTable / OverviewScreen / App (contract, not coverage-theatre); enforce a
coverage floor (back + front) in CI.
**Done:** UI behaviour is tested; a coverage regression fails CI. Gate to Phase 3.

### 3 — Structural refactor  · M · risk: low (guarded by Phase 2)  · ✅ DONE (PR #61, #62)
Split the god-files: `FindingsTable.tsx` (logic → `lib/`, components → files) and
`server.py` (`APIRouter` per domain). Add an ADR if the API shape changes.
**Done:** no file >~250 LOC without reason; module boundaries documented; Phase 2
+ pytest tests stay green (proof the refactor was behaviour-preserving).

### 4 — Crawler reality, performance, threat model  · M/L · risk: medium  · ✅ DONE (PR #63)
Local fixture server exercising redirects, gzip, latin-1/Shift-JIS, sitemap-index,
robots crawl-delay, CDN patterns — full `fetch→detect→report` e2e, deterministic
in CI. Clean up remaining detection noise (`font:` shorthand remnants, generics).
Characterise performance and **write the numbers** into `methodology.md`
(pages/sec, behaviour at N domains, memory bound). Complete `SECURITY.md` threat
model. One-off manual SSRF-guard check against real DNS.
**Done:** reality e2e in CI; documented performance profile with numbers; explicit
threat model.

### 5 — Detection accuracy validation  · M · risk: low  · PRIMARY EVIDENCE  · ✅ DONE (PR #64)
Hand-verified page-level ground truth for N pages (view-source / DevTools). Measure
detection **precision / recall**: real-and-previously-unknown found (TP), parser
artifacts (FP), missed (FN). This turns the "we found unknown fonts" anecdote into
a number. Independent of the judgement layer, so it runs here.
**Done:** published precision/recall for detection in `methodology.md`.

### 6 — Deterministic verdicts (ADR 0003)  · L · risk: medium (core change)  · ✅ DONE
The one judgement-layer change. Replace the weighted engine with the decision
table: privacy verdict + licence verdict (`COVERED` / `VIOLATION` / `OPEN` /
`UNKNOWN` / `SYSTEM`) with explicit reasons; soft signals become evidence notes.
Migrate `rules.yaml` (drop `scoring:`/weights), report schema, and UI (band →
verdict + reason). Deterministic → unit-testable: known input → expected verdict,
pinned in the suite.
**Done:** score removed; verdicts + reasons everywhere; rule tests green; schema
& config migration documented.

### 7 — Human review, limitations, process writeup, freeze  · S/M · process  · ✅ DONE
A human reviews the now-final core (`engine`/verdicts, `registry`, `fetcher`,
`scan`) — not another AI session; recorded. Add `LIMITATIONS.md` ("what this is
NOT"). Make `methodology.md` an honest account of how it was built (Claude Code,
phases, gates, guards, human review, validation) — the benchmark exhibit. Tag an
`infra-stable` reference (e.g. v0.4.0); verdict rules formally frozen.
**Done:** core human-reviewed; limits and process documented; stable reference tag.
- ✅ `LIMITATIONS.md` and `methodology.md` done. ✅ Operator reviewed the core and
  used the tool on real domains; the checks caught six real issues along the way
  (detection: `@import`, JS-injected, `fsType`, `local()`-only, `data:` URIs; a UI
  scan-timeout), each fixed with tests. ✅ Core signed off — **verdict rules frozen**
  and tagged **`v0.4.0`**. Next: Phase 8.

### 8 — Verdict-rule validation on ground truth  · M · risk: low
On the stable, reviewed tool. Labelled set (20–30 real domains, human verdict:
allowed / violation / unknown). Deterministic harness (in repo, reproducible via
one command) compares tool verdicts to labels; false-negatives reported
separately. This confirms the *rules* are right — not weight tuning. Publish
results, including where the tool is wrong, in `methodology.md`.
**Done:** verdicts validated against human judgement, reproducible, with a stated
margin of error.

## What a CTO will probe → where it's answered

- "How do you know it's correct?" → Phases 2/4/5/8 (evidence) + 7 (human review).
- "How does it scale?" → Phase 4 (numbers).
- "Security?" → Phase 4 (threat model; SSRF already done).
- "Is the AI output trustworthy?" → Phase 7 (transparent process + review + limits).
- "Does the judgement mean anything?" → ADR 0003 + Phases 6/8 (deterministic +
  validated, `UNKNOWN` owned).
- "Architecture?" → Phase 3 (split + ADRs).
- "Reproducible?" → Phase 8 (one command).
- "Over-engineered?" → guardrail: no new features, no speculative abstraction.

## Rough effort

Phases 1–7 ≈ 10–14 working days before Phase 8 is meaningful. Deliberately slower
than the initial build velocity — the benchmark defends the *process*, not speed.
