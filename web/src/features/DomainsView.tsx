import { useMemo, useState } from "react";
import { RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import type { Band, DomainReport, Status } from "../lib/api";

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <Card>
      <div className="text-2xl font-bold tabular-nums">{n}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </Card>
  );
}

interface DomainRow {
  domain: string;
  isLive: boolean;
  family: string;
  foundry: string | null;
  embeddings: string[];
  formats: string[];
  hosts: string[];
  subdomainHosts: string[];
  band: Band;
  status: Status;
}

function toRows(domains: DomainReport[]): DomainRow[] {
  const rows: DomainRow[] = [];
  for (const d of domains) {
    for (const f of d.fonts) {
      rows.push({
        domain: d.domain,
        isLive: d.is_live,
        family: f.family,
        foundry: f.foundry,
        embeddings: f.embeddings,
        formats: f.formats,
        hosts: f.hosts,
        subdomainHosts: d.subdomains,
        band: f.band,
        status: f.status,
      });
    }
  }
  return rows;
}

export function DomainsView({ domains }: { domains: DomainReport[] }) {
  const [domainFilter, setDomainFilter] = useState("all");
  const [band, setBand] = useState<Band | "all">("all");

  const totals = useMemo(
    () => ({
      domains: domains.length,
      live: domains.filter((d) => d.is_live).length,
      subdomains: domains.reduce((acc, d) => acc + d.subdomains.length, 0),
      pages: domains.reduce((acc, d) => acc + d.pages_scanned, 0),
    }),
    [domains],
  );

  const rows = useMemo(() => {
    return toRows(domains)
      .filter((r) => (domainFilter === "all" ? true : r.domain === domainFilter))
      .filter((r) => (band === "all" ? true : r.band === band));
  }, [domains, domainFilter, band]);

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

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium">Domain</span>
          <Select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)}>
            <option value="all">all</option>
            {domains.map((d) => (
              <option key={d.domain} value={d.domain}>
                {d.domain}
              </option>
            ))}
          </Select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Band</span>
          <Select value={band} onChange={(e) => setBand(e.target.value as Band | "all")}>
            <option value="all">all</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </Select>
        </label>
      </div>

      <div className="overflow-x-auto rounded-tk border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Fonts by domain</caption>
          <thead>
            <tr className="bg-canvas text-left">
              <th scope="col" className="px-4 py-2 font-semibold">
                Domain
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Font
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Foundry
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Embedding
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Format
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Hosts
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Band
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.domain}:${r.family}:${i}`} className="border-t border-stroke">
                <td className="px-4 py-2">
                  {r.domain}
                  {!r.isLive && <span className="ml-1 text-muted">(offline)</span>}
                </td>
                <td className="px-4 py-2 font-medium">{r.family}</td>
                <td className="px-4 py-2">{r.foundry ?? "—"}</td>
                <td className="px-4 py-2">{r.embeddings.join(", ") || "—"}</td>
                <td className="px-4 py-2">{r.formats.join(", ") || "—"}</td>
                <td className="px-4 py-2" title={r.hosts.join(", ")}>
                  {r.hosts.length}
                  {r.subdomainHosts.length > 0 && (
                    <span className="ml-1 text-muted">
                      ({r.subdomainHosts.length} sub)
                    </span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <RiskBadge band={r.band} />
                </td>
                <td className="px-4 py-2">{r.status}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-muted">
                  No fonts match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
