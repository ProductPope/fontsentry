# Classification reference

The verdict engine is **deterministic** (see [ADR 0003](adr/0003-deterministic-verdicts.md)):
no weights, no scores. Each font gets two verdicts, each with an explicit reason.
`config/rules.yaml` (copy from `config/rules.example.yaml`) holds only the
**classification data**; the decision table itself lives in `fontsentry/risk/`.

> The verdicts are a deterministic aid, **not legal advice**. `VIOLATION` or
> `NEEDS_CHECK` means a font is worth a human review — not a legal determination.

## The two verdicts

**License verdict** — one of:

- **OK** — no action: covered by a registry license, provably open, or a
  system/fallback font.
- **NEEDS_CHECK** — the honest default: no license on record and not provably open.
  Carries *evidence notes* (context) that inform but never decide.
- **VIOLATION** — a definite lapse: a declared license expired or is out of scope /
  over `max_domains`; a paid tier served with no cover; a self-host-prohibited font
  self-hosted with no cover.

**Privacy verdict** — derived from the delivery method (not configured here):
`self_hosted`, `third_party_api` (visitor IPs sent to a font CDN — a GDPR fact),
`mixed`, or `not_applicable` (system font).

## Decision order (first match wins)

1. Delivery is system-only → **OK** (no license question).
2. A matching registry entry: valid + in scope + within `max_domains` → **OK**;
   otherwise (expired / out of scope / over limit) → **VIOLATION**. *(A declared,
   lapsed license is a violation — the registry check precedes the open check.)*
3. No registry cover, but provably open (open license string, free owner, or a known
   open family) → **OK**.
4. No cover and not open: the font's OS/2 `fsType` forbids web embedding, a paid
   tier by name, or a self-host-prohibited font self-hosted → **VIOLATION**.
5. Otherwise → **NEEDS_CHECK** with evidence notes.

## Classification config keys

| Key | Role | Effect |
| --- | --- | --- |
| `open_license_patterns` | provably-open | substrings in the name-table license/copyright → OK |
| `free_owners` | provably-open | owners whose fonts are free → OK |
| `open_families` | provably-open | families that are open but ship no license string → OK (each with `contains_all` / `excludes`) |
| `paid_tier_families` | violation | family names that indicate a paid tier (e.g. Font Awesome Pro) → VIOLATION when uncovered |
| `self_host_prohibited` | violation | `owners` / `families` whose license forbids self-hosting → VIOLATION when self-hosted and uncovered |
| `paid_cdns` | evidence | embedding methods (e.g. `adobe_fonts`) that add a "paid CDN, no license" note |
| `desktop_formats` | evidence | formats (e.g. `ttf`, `otf`) that add a "desktop format on the web" note |
| `subset_max_glyphs` | evidence | below this glyph count a web font adds a "looks subsetted" note |

Evidence-note keys (`paid_cdns`, `desktop_formats`, `subset_max_glyphs`) only add
context to `NEEDS_CHECK`; they never by themselves make a font a `VIOLATION`.

## Editing and validating

Edit `config/rules.yaml`, then check it:

```bash
fontsentry rules validate --file config/rules.yaml
```

Adding a genuinely new *kind* of check (not just data) means adding a helper in
`fontsentry/risk/rules.py`, wiring it into the decision table in
`fontsentry/risk/engine.py`, and a deterministic test (known input → expected
verdict) in `tests/test_risk_engine.py`.
