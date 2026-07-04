# 2. Risk-scoring model

- Status: Superseded by [ADR 0003](0003-deterministic-verdicts.md)
- Date: 2026-06-30

> Superseded 2026-07-04: the weighted score was unvalidated/unfalsifiable and is
> replaced by deterministic verdicts. Retained for history.

## Context

The tool must estimate the probability that a detected font is used in violation
of its license. "Probability" here is a heuristic, not a legal determination. The
scoring must be transparent, tunable by non-developers, and able to express
cross-domain conditions (e.g. a license that permits at most N domains), which can
only be evaluated after the whole crawl.

## Decision

A **data-driven, additive rule engine**:

- **Rule data lives in `rules.yaml`**; **rule mechanics live in code.** Each rule
  has an `id`, `description`, `weight`, `confidence`, and a `when` condition whose
  `type` names one predicate from a fixed, auditable vocabulary
  (`fontsentry/risk/rules.py`). Parameters (formats, owner lists, CDN sets,
  thresholds) are pure data. Arbitrary code is never executed from YAML.
- **Aggregation precedes scoring.** Per-page detections are merged into one
  identity per font family across all domains, so cross-domain predicates such as
  `max_domains_exceeded` see every domain.
- **Scoring is additive then normalized.** Each firing rule contributes
  `weight × confidence` points; the raw sum is normalized to 0–100 via a
  configurable `scoring.max_raw` and clamped, then mapped to low/medium/high bands
  whose thresholds also come from `rules.yaml`.
- **Suppression is separate from scoring.** A finding is RESOLVED only when a
  registry license genuinely covers it (matching owner+family, not expired, every
  observed domain allowed, within `max_domains`); otherwise it is OPEN with a
  reason. Suppression decides *alerting*; the score still explains *why*.
- **Evidence-gated predicates.** Rules that assert "commercial" or "missing
  copyright" only fire when font-file metadata was actually read, so unreachable
  files do not produce false positives.

## Alternatives considered

- *Hardcoded scoring*: rejected — not tunable without code changes, fails the
  "editable by the user" requirement.
- *ML classifier*: rejected — opaque, needs labelled data, and undermines the
  "show your work" transparency this tool depends on.

## Consequences

- Anyone can add or retune a rule by editing YAML; only a genuinely new *kind* of
  check needs code (a new predicate) plus a test and a docs entry.
- Weights and thresholds are judgement calls; defaults are a starting point, not
  ground truth. The output is always framed as a heuristic estimate.
- Because scoring is additive, interactions between rules are easy to reason about
  and the triggered-rule list makes every score explainable.
