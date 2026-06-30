import type { ReactNode } from "react";

function Item({ q, children }: { q: string; children: ReactNode }) {
  return (
    <details className="group rounded-tk border border-stroke bg-surface">
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
      <h2 className="text-base font-semibold">How to read this table</h2>

      <Item q="What does each column mean?">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Host</strong> — the exact host the font was found on. Subdomains appear as
            their own rows, tagged <em>subdomain</em>.
          </li>
          <li>
            <strong>Font / Foundry</strong> — the family and its maker (from the font file's name
            table, when reachable).
          </li>
          <li>
            <strong>Embedding</strong> — how the font is delivered (see below).
          </li>
          <li>
            <strong>Format</strong> — the file format (woff2, woff, ttf, otf, eot).
          </li>
          <li>
            <strong>Band / Status</strong> — risk level and whether it is an open finding or
            covered by a license (see below).
          </li>
        </ul>
      </Item>

      <Item q="What do High / Medium / Low mean?">
        A risk <strong>band</strong> derived from a 0–100 score: the more (and stronger) the rules
        a font triggers, the higher the score. High = most worth a human checking the license,
        Low = little signal. This is a <strong>heuristic estimate, not legal advice</strong> — a
        high band does not mean infringement, only that it is worth reviewing. Thresholds are
        configurable in <code>config/rules.yaml</code>.
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

      <Item q="Open vs Resolved — does the status change by itself?">
        Yes. Status is <strong>recomputed on every scan</strong>; it is never edited by hand. A
        finding is <strong>Resolved</strong> automatically when a matching entry in your license
        registry covers it — same foundry + family, the domain is allowed, the domain count is
        within the license limit, and the license has not expired. Otherwise it stays{" "}
        <strong>Open</strong> with a reason.
      </Item>

      <Item q="How do I change the status for a domain?">
        You don't set it directly — you record the license. Add an entry to{" "}
        <code>registry/licenses.yaml</code> (copy from{" "}
        <code>registry/licenses.example.yaml</code>) with the <code>foundry</code>,{" "}
        <code>family</code>, the <code>allowed_domains</code> that include this domain, an optional{" "}
        <code>max_domains</code>, and <code>valid_until</code>. On the next audit that font on that
        domain flips to Resolved.
      </Item>

      <Item q="How do I load a list of domains to scan?">
        Edit <code>config/targets.yaml</code> (copy from <code>config/targets.example.yaml</code>),
        then run a <em>real</em> audit:
        <pre className="mt-2 overflow-x-auto rounded-tk border border-stroke bg-canvas p-3 text-ink">
          {`targets:
  - domain: "example.com"
    subdomain_seeds: ["blog.example.com"]
  - domain: "example.org"`}
        </pre>
        Subdomains are also discovered passively (sitemap + links); the tool never brute-forces.
      </Item>
    </section>
  );
}
