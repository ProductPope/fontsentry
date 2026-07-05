# Limitations — what FontSentry is *not*

FontSentry is a deterministic **aid**, not an authority. This page states, plainly,
what it does not do and where it is known to be incomplete. Being honest about the
boundary is part of the point (see [docs/methodology.md](docs/methodology.md)).

## Not legal advice

The license and privacy verdicts are derived from observable facts by a fixed
decision table. A `VIOLATION` or `NEEDS_CHECK` means "worth a human checking the
license", **not** a legal determination of infringement or liability. Always confirm
with the font's owner or your legal team. `NEEDS_CHECK` is the honest default when
the license cannot be established from the evidence.

## Detection boundary

The crawler reads **static** HTML and CSS: `@font-face`, `@import`, `<link>`
stylesheets, and font preloads. Consequences:

- **JavaScript-injected fonts.** A font loaded only by a script (e.g. the
  CSS Font Loading API, or a `<link>`/stylesheet appended at runtime) has no
  static `@font-face` to read. When the family is still referenced in a
  `font-family` declaration it is reported as **UNKNOWN delivery → NEEDS_CHECK**
  with an evidence note; when it appears nowhere in static CSS it is **not
  detected at all**. Full rendering requires the optional Playwright fallback
  (the `browser` extra), which is **off by default** — it is heavy (a headless
  browser) and only helps a minority of pages.

- **OS/2 `fsType` — Preview & Print is not a violation.** We flag the
  **Restricted-License** bit (`0x0002`) — the foundry's unambiguous "no embedding"
  signal — as a `VIOLATION`. The **Preview & Print** bit (`0x0004`) is deliberately
  **not** treated as a violation: it is a common default (many legitimately
  web-licensed fonts ship it), so flagging it would manufacture false positives.
  This is a conscious precision-over-recall choice.

- **woff2 metadata needs brotli.** Reading a woff2 font's name table requires the
  `brotli` dependency (bundled). Without it, woff2 files are detected but their
  embedded license/owner strings cannot be read, so such fonts lean toward
  `NEEDS_CHECK`.

- **Font metadata can be absent or wrong.** Name-table strings (owner, copyright,
  license) are set by whoever built the file and may be stripped or inaccurate.
  Verdicts that depend on them degrade gracefully to `NEEDS_CHECK`, never a false
  `OK`.

## Verdict-rule validation

The decision table is deterministic and unit-tested (known input → expected
verdict). Whether the *rules themselves* match real-world licensing across a broad,
labelled sample is a separate question, validated against ground truth (roadmap
Phase 8). Treat the verdicts as a triage signal, not ground truth, until then.

## Scope

- **Local, single-user.** Not designed for multi-user or networked deployment; the
  web UI binds to `127.0.0.1` only and has no authentication (see `SECURITY.md`).
- **Recurring scheduling is Windows-only** (Task Scheduler); other platforms would
  need cron/launchd.
- FontSentry audits **fonts**. It does not assess other asset licensing (images,
  icons-as-images, video) or non-font web compliance.
