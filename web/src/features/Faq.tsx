import type { ReactNode } from "react";

function Item({ q, children }: { q: string; children: ReactNode }) {
  return (
    <details className="group rounded-card border border-stroke bg-surface">
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 font-medium">
        {q}
        <span aria-hidden="true" className="text-muted group-open:hidden">
          +
        </span>
        <span aria-hidden="true" className="hidden text-muted group-open:inline">
          −
        </span>
      </summary>
      <div className="border-t border-stroke px-4 py-3 text-sm text-muted">{children}</div>
    </details>
  );
}

export function Faq() {
  return (
    <section aria-label="Help" className="space-y-2">
      <h2 className="text-base font-semibold">Help</h2>

      <Item q="Fonts view vs Domains view?">
        Same audit, two perspectives. <strong>Fonts</strong> lists each font once, aggregated
        across every domain it appears on (expand a row for the reason and metadata).{" "}
        <strong>Domains</strong> lists fonts per host — each domain and subdomain as its own
        rows — plus how many domains were scanned, how many are live, and how many subdomains
        were found.
      </Item>

      <Item q="What do the columns mean?">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Font / Owner</strong> — the family and its maker (from the font file's name
            table, when reachable).
          </li>
          <li>
            <strong>Embedding</strong> — how the font is delivered (see below).
          </li>
          <li>
            <strong>Format</strong> — the file format (woff2, woff, ttf, otf, eot).
          </li>
          <li>
            <strong>Domains / Host</strong> — in Fonts, the number of domains the font is on; in
            Domains, the exact host (subdomains tagged <em>subdomain</em>).
          </li>
          <li>
            <strong>License / Privacy</strong> — the two deterministic verdicts (see below).
          </li>
        </ul>
      </Item>

      <Item q="What do OK / Need check / Violation mean?">
        The <strong>license verdict</strong> comes from a fixed decision table (no scores):{" "}
        <strong>OK</strong> — covered by your registry, provably open, or a system font;{" "}
        <strong>Need check</strong> — no license on record and not provably open (the honest
        default; the row lists what we noticed); <strong>Violation</strong> — a definite lapse
        (an expired or out-of-scope license, a paid tier, or self-hosting a font that forbids it).
        This is a <strong>deterministic aid, not legal advice</strong> — a verdict is a prompt to
        review, not a legal determination.
      </Item>

      <Item q="What is the Privacy verdict?">
        Independent of the license: how the font is delivered. <strong>Self-hosted</strong> leaks
        nothing; <strong>Third-party</strong> (Google Fonts API, Adobe, a CDN) sends each visitor's
        IP off-site — a GDPR/RODO concern even when the font is free. Self-host the files to fix it.
      </Item>

      <Item q="What is &quot;Embedding&quot;?">
        How the font reaches the page:
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>self_hosted</strong> — served from the site's own host.
          </li>
          <li>
            <strong>google_fonts / adobe_fonts / monotype</strong> — a known font provider/CDN.
          </li>
          <li>
            <strong>other_cdn</strong> — some other third-party host.
          </li>
          <li>
            <strong>system</strong> — a local fallback font (not embedded; excluded here).
          </li>
        </ul>
      </Item>

      <Item q="Does the verdict change by itself?">
        Yes. Verdicts are <strong>recomputed on every scan</strong>; they are never edited by hand.
        A font becomes <strong>OK</strong> automatically when a matching entry in your license
        registry covers it — same owner + family, the domain is allowed, the domain count is within
        the license limit, and the license has not expired.
      </Item>

      <Item q="How do I clear a font for a domain?">
        You don't set the verdict directly — you record the license. Add an entry to{" "}
        <code>registry/licenses.yaml</code> (copy from{" "}
        <code>registry/licenses.example.yaml</code>) with the <code>owner</code>,{" "}
        <code>family</code>, the <code>allowed_domains</code> that include this domain, an optional{" "}
        <code>max_domains</code>, and <code>valid_until</code>. On the next audit that font on that
        domain turns <strong>OK</strong>.
      </Item>

      <Item q="How do I load a list of domains to scan?">
        Edit <code>config/targets.yaml</code> (copy from <code>config/targets.example.yaml</code>),
        then run a <em>real</em> audit:
        <pre className="mt-2 overflow-x-auto rounded-tk border border-stroke bg-sunken p-3 font-mono text-ink">
          {`targets:
  - domain: "example.com"
    subdomain_seeds: ["blog.example.com"]
  - domain: "example.org"`}
        </pre>
        Subdomains are discovered passively (sitemap + links). You can also tick{" "}
        <strong>Find subdomains</strong> when starting an audit to pull public subdomains from
        Certificate Transparency logs — that one queries an external service, so it is off by
        default. The tool never brute-forces DNS.
      </Item>
    </section>
  );
}
