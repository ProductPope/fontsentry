import { useMemo, useState } from "react";
import { RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import type { DomainReport } from "../lib/api";

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <Card>
      <div className="text-2xl font-bold tabular-nums">{n}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </Card>
  );
}

function DomainCard({ domain }: { domain: DomainReport }) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <span className="font-semibold">
          {open ? "▾ " : "▸ "}
          {domain.domain}
        </span>
        <span className="flex items-center gap-3 text-sm text-muted">
          <span className={domain.is_live ? "text-band-low" : "text-muted"}>
            {domain.is_live ? "live" : "offline"}
          </span>
          <span className="tabular-nums">{domain.pages_scanned} pages</span>
          <span className="tabular-nums">{domain.subdomains.length} subdomains</span>
          <span className="tabular-nums">{domain.fonts.length} fonts</span>
        </span>
      </button>

      {open && (
        <div className="mt-3 grid gap-4 border-t border-stroke pt-3 text-sm sm:grid-cols-2">
          <div>
            <h3 className="mb-1 font-semibold">Hosts</h3>
            <ul className="space-y-1">
              {domain.live_hosts.map((h) => (
                <li key={h}>
                  {h}
                  {domain.subdomains.includes(h) && (
                    <span className="ml-1 text-muted">(subdomain)</span>
                  )}
                </li>
              ))}
              {domain.live_hosts.length === 0 && <li className="text-muted">none reachable</li>}
            </ul>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Fonts used</h3>
            {domain.fonts.length > 0 ? (
              <ul className="space-y-1">
                {domain.fonts.map((f) => (
                  <li key={f.family} className="flex items-center gap-2">
                    <RiskBadge band={f.band} />
                    <span>{f.family}</span>
                    {f.foundry && <span className="text-muted">· {f.foundry}</span>}
                    <span className="text-muted">({f.status})</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">no web fonts detected</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

export function DomainsView({ domains }: { domains: DomainReport[] }) {
  const totals = useMemo(
    () => ({
      domains: domains.length,
      live: domains.filter((d) => d.is_live).length,
      subdomains: domains.reduce((acc, d) => acc + d.subdomains.length, 0),
      pages: domains.reduce((acc, d) => acc + d.pages_scanned, 0),
    }),
    [domains],
  );

  if (domains.length === 0) {
    return <p className="text-muted">This run has no domain data (older report).</p>;
  }

  return (
    <div className="space-y-4">
      <section aria-label="Domain summary" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat n={totals.domains} label="Domains" />
        <Stat n={totals.live} label="Live" />
        <Stat n={totals.subdomains} label="Subdomains" />
        <Stat n={totals.pages} label="Pages scanned" />
      </section>

      <section aria-label="Domains" className="space-y-3">
        {domains.map((d) => (
          <DomainCard key={d.domain} domain={d} />
        ))}
      </section>
    </div>
  );
}
