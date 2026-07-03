# Risk rules reference

The risk engine is driven by `config/rules.yaml` (copy from
`config/rules.example.yaml`). This page documents the scoring model, every default
rule, and how to add your own.

> The score is a **heuristic estimate, not legal advice**. A high score means a
> font is worth a human checking — not that infringement has occurred.

## Scoring model

1. Per-page detections are aggregated into one identity per **(family, owner)**
   across all scanned domains (a different owner for the same family name is a
   different font, so a benign owner can't mask a commercial one).
2. Every rule whose condition matches contributes `weight × confidence` points.
3. The raw sum is normalized: `score = min(100, 100 × raw / scoring.max_raw)`.
4. The score maps to a band via `scoring.bands` (`medium` and `high` thresholds;
   below `medium` is `low`).
5. A font served via `@font-face` but not applied to any text has its score
   **halved** — unless a rule marked `hard: true` fired (e.g. expired/over-limit
   license, paid tier), which is a real violation regardless of rendering.

```yaml
scoring:
  max_raw: 90       # raw weighted sum that maps to a score of 100 (clamped)
  bands:
    medium: 30
    high: 60
```

## Condition types (predicate vocabulary)

Implemented in `src/fontsentry/risk/rules.py`. Parameters come from the rule.

| `type` | Fires when | Params |
| --- | --- | --- |
| `format_on_web` | A listed font format is served via @font-face (embedding ≠ system) | `formats` |
| `commercial_unregistered` | Metadata present, not an open license, owner not free, family not a known-open family, and no registry entry | `open_license_patterns`, `free_owners`, `open_families` |
| `family_name_matches` | The family name contains every `contains_all` substring and none in `excludes` (e.g. a paid tier like Font Awesome Pro) | `contains_all`, `excludes` |
| `max_domains_exceeded` | A matching registry entry's `max_domains` is exceeded across the crawl | — |
| `self_host_prohibited` | Self-hosted and the owner/family is on a prohibited list | `owners`, `families` |
| `paid_cdn_unregistered` | Served from a listed paid CDN with no registry entry | `cdns` |
| `missing_name_field` | A listed name-table field is missing/empty (metadata present) | `fields` |
| `license_expired` | A matching registry entry has expired (`valid_until` past) | — |
| `subset_signal` | A web-format font has fewer glyphs than a threshold (low confidence) | `max_glyphs` |

Predicates that need evidence (commercial, missing-field, subset) only fire when
the font file was actually downloaded and parsed, avoiding false positives on
unreachable files.

## Default rules

The shipped `rules.example.yaml` defines: `desktop-format-on-web`,
`commercial-no-registry`, `max-domains-exceeded`, `self-host-prohibited`,
`paid-cdn-no-registry`, `missing-copyright`, `expired-license`, `paid-tier-in-name`,
and `subset-signal`.
Each is documented with an inline comment in that file.

## Adding a rule

1. Add an entry to `rules.yaml` with `id`, `description`, `weight`, `confidence`,
   an optional `hard: true` (a definite violation — its score is not halved for a
   served-but-unapplied font), and a `when` block referencing a condition `type`.
2. If you need a new *kind* of check, add a predicate to
   `src/fontsentry/risk/rules.py` and register it in `PREDICATES`.
3. Add a unit test in `tests/test_risk_engine.py` (offline, fixture-based).
4. Document it here and validate: `fontsentry rules validate --file config/rules.yaml`.
