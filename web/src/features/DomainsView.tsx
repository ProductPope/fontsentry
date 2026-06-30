import { useMemo, useState } from "react";
import { RiskBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import type { Band, DomainReport, Status } from "../lib/api";
import { Faq } from "./Faq";

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <Card>
      <div className="text-2xl font-bold tabular-nums">{n}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </Card>
  );
}

interface HostRow {
  host: string;
  domain: string;
  isSubdomain: boolean;
  family: string;
  foundry: string | null;
  embeddings: string[];
  formats: string[];
  band: Band;
  status: Status;
}

// One row per (host, font): subdomains become their own rows.
function toRows(domains: DomainReport[]): HostRow[] {
  const rows: HostRow[] = [];
  for (const d of domains) {
    for (const f of d.fonts) {
      for (const host of f.hosts) {
        rows.push({
          host,
          domain: d.domain,
          isSubdomain: d.subdomains.includes(host),
          family: f.family,
          foundry: f.foundry,
          embeddings: f.embeddings,
          formats: f.formats,
          band: f.band,
          status: f.status,
        });
      }
    }
  }
  return rows.sort(
    (a, b) => a.host.localeCompare(b.host) || a.family.localeCompare(b.family),
  );
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
          <caption className="sr-only">Fonts by host</caption>
          <thead>
            <tr className="bg-canvas text-left">
              <th scope="col" className="px-4 py-2 font-semibold">
                Host
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
                Band
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.host}:${r.family}:${i}`} className="border-t border-stroke">
                <td className="px-4 py-2">
                  {r.host}
                  {r.isSubdomain && <span className="ml-1 text-muted">(subdomain)</span>}
                </td>
                <td className="px-4 py-2 font-medium">{r.family}</td>
                <td className="px-4 py-2">{r.foundry ?? "—"}</td>
                <td className="px-4 py-2">{r.embeddings.join(", ") || "—"}</td>
                <td className="px-4 py-2">{r.formats.join(", ") || "—"}</td>
                <td className="px-4 py-2">
                  <RiskBadge band={r.band} />
                </td>
                <td className="px-4 py-2">{r.status}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted">
                  No fonts match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Faq />
    </div>
  );
}
