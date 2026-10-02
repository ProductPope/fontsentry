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
  `@font-face`, decodes inline `data:` fonts, **scans the page's own JS bundles**
  for self-hosted font URLs (recovering fonts a SPA injects at runtime, as long as
  the URL is shipped as a string in a same-site bundle), and flags known
  third-party **loader scripts** (Adobe Typekit, Font Awesome kit, …) as a
  third-party privacy finding. What still slips through: a font whose URL never
  appears in the static HTML/CSS *or* a same-site bundle — e.g. a URL assembled at
  runtime from string fragments, or one that lives only in a lazily-loaded route
  chunk not referenced from the shell. When a family is referenced in
  `font-family` but never defined and never recovered, it is reported as **UNKNOWN
  delivery → NEEDS_CHECK**, not a clean result. Fully rendering the page in a
  headless browser would close this last gap, but that is **deliberately not
  built** — the static bundle scan already covers the common case, and a headless
  browser is a heavyweight, less-deterministic dependency we don't add until it's
  shown necessary (see [ADR 0004](docs/adr/0004-spa-font-discovery.md); the `browser`
  extra is a placeholder seam only). When you have the site's source,
  `fontsentry scan-source PATH` sidesteps rendering entirely: it reads the font
  files straight from a checked-out repo, so it finds self-hosted fonts regardless
  of how the app loads them at runtime.

- **`@import` conditions are ignored.** An imported stylesheet is fetched and its
  fonts reported even when the `@import` carries a media/supports condition
  (`@import url(print.css) print`). This is deliberate for licensing: browsers
  download non-matching-media imports anyway, so the font is served regardless
  of whether it renders on screen.

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
verdict). Whether the *rules themselves* match real-world licensing is a separate
question, checked against a human-labelled ground truth in roadmap Phase 8 — see
the aggregate result in [docs/methodology.md](docs/methodology.md#verdict-validation-phase-8).
It is a modest, private, single-estate sample that confirms the *direction* of the
rules (no false clears); treat the verdicts as a triage signal, not ground truth.

## Scope

- **Local, single-user.** Not designed for multi-user or networked deployment; the
  web UI binds to `127.0.0.1` only and has no authentication (see `SECURITY.md`).
- **Recurring scheduling is supported on Windows (Task Scheduler) and Linux
  (cron) only.** On other platforms (macOS) the API returns `501`; schedule with
  `launchd` by hand.
- FontSentry audits **fonts**. It does not assess other asset licensing (images,
  icons-as-images, video) or non-font web compliance.
