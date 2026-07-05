# 4. SPA font discovery: static bundle scan, headless browser deferred

- Status: Accepted
- Date: 2026-07-05

## Context

Client-rendered single-page apps (Angular, Vue, React) wire up their
`@font-face` at runtime with JavaScript, so a font appears nowhere in the static
HTML/CSS a crawler reads. On a real payment-onboarding SPA the static scan found
**zero** fonts while the site self-hosted five families (two of them commercial).
This is the tool's largest detection-recall gap.

Two ways to close it:

1. **Static bundle scan** — the font files' URLs still ship as plain strings
   inside the app's own JS bundles. Fetch the same-site bundles, extract the font
   URLs, fetch each file, read its name table. No rendering.
2. **Headless-browser rendering** ("B2") — drive a real browser (Playwright),
   let the JS run, ask the rendered page which fonts it used.

## Decision

Ship the **static bundle scan** now (in `detect/bundle.py`, wired into
`detect_page`). **Defer headless-browser rendering deliberately** — do not build
it until the bundle scan is shown to miss cases that matter.

On the same real SPA, the bundle scan recovered all five families with full,
metadata-based verdicts — no browser. It stays within the tool's existing model:
deterministic, offline-friendly network I/O, no new heavyweight runtime.

## Why defer the headless browser

- **Weight.** Playwright pulls in a full browser (hundreds of MB). Everything else
  is a light, deterministic, offline-first pipeline. It is a different category of
  dependency and failure mode.
- **Speed & fragility.** Rendering is seconds per page vs a fraction for a static
  fetch, and a live browser adds timeouts, cookie walls, and bot blocks — less
  deterministic, the opposite of the tool's design goal.
- **It helps a shrinking minority.** The bundle scan already covers the common SPA
  case (self-hosted fonts whose URL is a string in a same-site bundle). What is
  left for a browser is a genuinely small residue (below).
- **Guardrail.** No heavy machinery before the cheap path is shown insufficient.

## What the bundle scan still misses (the residue a browser would need)

- A font URL **assembled at runtime** from string fragments (never a literal in
  the bundle).
- A font referenced **only in a lazily-loaded route chunk** not linked from the
  shell we fetch.
- Fonts injected by a **third-party loader** we don't fetch (already surfaced as a
  privacy finding by provider, not enumerated).

These are documented in `LIMITATIONS.md`. If real audits show this residue
matters, revisit B2 — the `browser` extra and `PlaywrightSettings` config
placeholder already exist as the seam to build against.

## Alternatives considered

- *Headless browser now (B2)* — rejected for the reasons above; kept as a future
  fallback, not a current dependency.
- *Parse `@font-face` out of the minified bundle text* — rejected: brittle against
  minified/obfuscated JS. Reading the **font file's own name table** (as for a
  statically declared font) is authoritative and reuses existing code.
- *Do nothing / require `scan-source`* — rejected: `scan-source` needs a checkout,
  which an external auditor scanning a live URL does not have.

## Consequences

- A live `scan` now catches most self-hosted SPA fonts with no new runtime.
- Fan-out is bounded (≤20 bundles/page, ≤50 font URLs); third-party scripts are
  never fetched (privacy-preserving and avoids arbitrary code hosts).
- The SPA limitation is narrowed, not eliminated; `LIMITATIONS.md` states exactly
  what remains and points to `scan-source` (offline, from a repo) as the other
  shipped answer.
