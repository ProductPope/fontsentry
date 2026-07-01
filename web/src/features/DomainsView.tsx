import { useMemo, useState } from "react";
import { RiskBadge, StatusText } from "../components/Badge";
import { Select } from "../components/Select";
import type { Band, DomainReport, Status } from "../lib/api";

// Comp table-header cell: small uppercase, faint, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

interface HostRow {
  host: string;
  domain: string;
  isSubdomain: boolean;
  family: string;
  owner: string | null;
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
          owner: f.owner,
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

      <div className="overflow-x-auto rounded-card border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Fonts by host</caption>
          <thead>
            <tr className="bg-surface2 text-left text-faint">
              <th scope="col" className={TH}>
                Host
              </th>
              <th scope="col" className={TH}>
                Font
              </th>
              <th scope="col" className={TH}>
                Owner
              </th>
              <th scope="col" className={TH}>
                Embedding
              </th>
              <th scope="col" className={TH}>
                Format
              </th>
              <th scope="col" className={TH}>
                Band
              </th>
              <th scope="col" className={TH}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.host}:${r.family}:${i}`} className="border-t border-stroke">
                <td className="px-4 py-2">
                  <span className="font-mono text-xs">{r.host}</span>
                  {r.isSubdomain && <span className="ml-1 text-faint">(subdomain)</span>}
                </td>
                <td className="px-4 py-2 font-medium">{r.family}</td>
                <td className="px-4 py-2">{r.owner ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.embeddings.join(", ") || "—"}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.formats.join(", ") || "—"}</td>
                <td className="px-4 py-2">
                  <RiskBadge band={r.band} />
                </td>
                <td className="px-4 py-2">
                  <StatusText status={r.status} />
                </td>
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
    </div>
  );
}
