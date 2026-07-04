# 3. Deterministic verdicts (retire weighted scoring)

- Status: Accepted
- Date: 2026-07-04
- Supersedes: ADR 0002 (risk-scoring model)

## Context

ADR 0002 introduced a weighted, additive risk score (low/medium/high from
`weight × confidence` sums). It has one fatal property for a tool meant to
withstand scrutiny: **the weights are unvalidated and unfalsifiable.** ADR 0002
itself admits "weights and thresholds are judgement calls … not ground truth."
A numeric score projects false precision onto what is frequently *unknown* (most
third-party fonts ship no readable license string and aren't in the registry).

The tool's proven value is **deterministic detection** — it surfaces web fonts
and how they're delivered, verified against reality. That layer needs no
heuristic. The judgement layer should be equally defensible: derived from facts,
auditable, and honest about what cannot be determined.

## Decision

Replace the score with **two independent, deterministic verdicts** per font,
each produced by a fixed decision procedure and carrying an explicit **reason**
(the facts that produced it). No weights, no thresholds, no calibration.

### Privacy verdict (from delivery method — fully deterministic)

- `SELF_HOSTED` — served from the site's own hosts; nothing leaks.
- `THIRD_PARTY` — served from a third party (Google Fonts API, Adobe, a CDN);
  each visitor's IP is sent off-site. A GDPR/RODO fact, independent of licence.
- `MIXED` — both, across pages.
- `NOT_APPLICABLE` — system/fallback font; nothing is fetched.

(This is the existing `PrivacyClass`, promoted to a first-class verdict.)

### Licence verdict (deterministic classification — `UNKNOWN` is first-class)

- `COVERED` — a registry entry matches (owner+family), is valid (not expired),
  every observed host is in scope, within `max_domains`.
- `VIOLATION` — a *definite* fact, one of: matched registry entry expired;
  matched but out-of-scope domain or over `max_domains`; a paid tier named in the
  family (e.g. "… Pro") served with no cover; a self-host-prohibited owner/family
  self-hosted with no cover.
- `OPEN` — provably open: an open-licence string (OFL/Apache/…), a known-open
  family, or a free owner. No licence needed.
- `UNKNOWN` — none of the above can be established (no readable licence, not in
  the registry, not provably open or violating). **The honest default.** Carries
  *evidence notes* explaining why (desktop format on the web, no licence string,
  possible subsetting, served-but-not-applied) — notes inform, they do not decide.

### Decision order (documented, first match wins)

1. delivery is system-only → licence verdict `SYSTEM` (no licence question).
2. registry: matched+valid+in-scope → `COVERED`; matched+expired or
   matched+out-of-scope → `VIOLATION`.
3. no valid cover: provably open → `OPEN`; paid-tier-by-name or
   self-host-prohibited → `VIOLATION`; otherwise → `UNKNOWN` (+ evidence notes).

Registry declaration precedes the open-evidence check: if the operator declared a
font as licensed and it lapsed, that is a `VIOLATION`, not silently `OPEN`.

### Configuration

`rules.yaml` keeps the **classification data** (open-licence patterns, free-owner
list, open-family and paid-tier patterns, paid-CDN set, self-host-prohibited
lists, desktop-format list, subset threshold) — mechanics stay in code. The
`scoring` block (`max_raw`, band thresholds) and per-rule `weight`/`confidence`
are **removed** (breaking config change; report schema bump; `RiskBand` →
`Verdict` in the models).

## Alternatives considered

- *Keep the weighted score* — rejected: the core objection (unvalidated,
  unfalsifiable weights) is exactly what this ADR removes.
- *Naive binary "allowed: yes/no"* — rejected: it manufactures certainty the tool
  does not have. You cannot deterministically prove "allowed" without knowing the
  licence terms, which are frequently absent. `UNKNOWN` must be first-class.
- *ML classifier* — rejected (as in ADR 0002): opaque, needs labelled data,
  undermines the "show your work" transparency.

## Consequences

- **Less code, more defensible.** The scoring arithmetic, `max_raw`, band
  thresholds and weight tuning are deleted; the engine becomes a readable,
  unit-testable decision table. Every verdict maps to an explicit `if/then` a
  reviewer can inspect.
- **Honest about limits.** `UNKNOWN` is stated, not hidden behind a number.
- **Validation changes shape.** What ADR 0002 left as unresolved weight
  calibration becomes ordinary deterministic tests: known inputs → expected
  verdict, pinned in the suite (fits the offline-test philosophy). No ground-truth
  calibration is required to trust the *rules*; a labelled set is still useful to
  confirm the *rules themselves* are right.
- **No fine ranking.** Sorting is by verdict severity
  (`VIOLATION` > third-party privacy > `UNKNOWN` > `OPEN` > `COVERED` > `SYSTEM`),
  not a 0–100 number. This is a deliberate loss of false precision.
- **Breaking changes:** config (`rules.yaml`), report schema, and the UI
  (band badge → verdict + reason). Requires a migration and version bump.
