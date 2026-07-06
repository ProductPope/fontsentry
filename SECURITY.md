# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab), not as a public
issue. Include steps to reproduce and the affected version/commit. We aim to
acknowledge within a few days.

## Threat model

FontSentry is a **local, single-user** tool. The web UI (`fontsentry serve`)
binds `127.0.0.1` only and has no authentication — the trust boundary is the
local machine. The interesting attack surface is the **outbound crawler**, which
fetches untrusted content from arbitrary domains.

In scope:

- **SSRF via the crawler.** The crawler follows font/CSS `src`, page links, HTTP
  redirects, and Certificate-Transparency results — all attacker-influenceable.
  Mitigation: `crawl.block_private_hosts` (default on) refuses hosts that resolve
  to loopback/private/link-local/reserved addresses; redirects are followed
  manually and re-checked per hop. Disable only to audit an internal site.
- **Resource exhaustion.** Fetched bodies are streamed and capped
  (`crawl.max_response_bytes`, default 25 MB), bounding decompressed size; the
  proof-upload endpoint streams with a hard cap. Every state-changing request
  body is size-capped (10 MB; workspace imports 250 MB) — declared length is
  checked up front and the raw-body import endpoints also enforce the cap while
  streaming. A restored workspace zip is bounded before extraction (entry count
  and total declared decompressed size — zip-bomb guard), and every entry path
  is validated before anything is written.
- **Untrusted parsing.** HTML/CSS/font bytes from the network are parsed; a
  malformed font is caught and surfaced, never crashing the scan. Font name-table
  strings are treated as untrusted (HTML report auto-escapes; CSV neutralizes
  formula-injection).
- **Path traversal.** Run-id and proof-file paths are resolved and confined to
  their directory.
- **Cross-origin state change.** The API rejects requests whose `Origin` is not
  localhost, and `Sec-Fetch-Site: cross-site`.

Out of scope:

- Multi-user / networked deployment (the tool is not designed to be exposed).
- The **accuracy of licence/privacy verdicts** — a heuristic/deterministic
  estimate, explicitly not legal advice (see `docs/adr/0003-deterministic-verdicts.md`).
- Real user data: never committed (see `.gitignore` and `CLAUDE.md`).
