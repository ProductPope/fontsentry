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

- **JavaScript-injected fonts and client-rendered (SPA) pages.** A font loaded
  only by a script (the CSS Font Loading API, a `<link>`/stylesheet appended at
  runtime), or a page whose content is rendered entirely client-side with no SSR,
  has no static `@font-face` to read. FontSentry does what it can statically: it
  follows `@import`, reads preloaded font files even without a matching
  `@font-face`, decodes inline `data:` fonts, and flags known third-party
  **loader scripts** (Adobe Typekit, Font Awesome kit, …) as a third-party
  privacy finding. But a font that appears nowhere in the static HTML/CSS — common
  on pure client-rendered SPAs — is **not detected**. When a family is referenced
  in `font-family` but never defined, it is reported as **UNKNOWN delivery →
  NEEDS_CHECK**, not a clean result. Full rendering requires the optional
  Playwright fallback (the `browser` extra), **off by default** — it is heavy (a
  headless browser) and only helps a minority of pages. When you have the site's
  source, `fontsentry scan-source PATH` sidesteps this entirely: it reads the font
  files straight from a checked-out repo, so it finds self-hosted fonts regardless
  of how the app loads them at runtime.

- **Loader scripts name the provider, not the fonts.** For a recognized loader
  script we surface the third-party provider (a GDPR/privacy fact) but cannot
  enumerate the individual fonts it injects at runtime without a browser.

- **Own asset domains.** A font on a separate domain you control (an asset CDN like
  `assets.mybrand.net`) is treated as third-party by default. Declare such hosts in
  `crawl.self_hosted_hosts` so they count as first-party (no false privacy leak).

- **Bot-protected sites.** A site behind a challenge (Cloudflare, WAF, aggressive
  bot filtering) may return a challenge page or `403` to the polite crawler; its
  fonts then go undetected. This fails safe (nothing is reported), not loud.

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
