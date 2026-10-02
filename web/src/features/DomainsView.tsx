import { useEffect, useMemo, useState } from "react";
import { Select } from "../components/Select";
import { api } from "../lib/api";
import type { DomainReport, LicenseVerdict } from "../lib/api";
import { firstSeenKey, toRows } from "../lib/domains";
import { HostFontRow } from "./HostFontRow";

// Comp table-header cell: small uppercase, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

const COLUMNS = [
  "Host",
  "Font",
  "Owner",
  "Embedding",
  "Format",
  "Source",
  "License",
  "Privacy",
  "First seen",
];

export function DomainsView({
  domains,
  source = "real",
}: {
  domains: DomainReport[];
  source?: "real" | "demo";
}) {
  const [domainFilter, setDomainFilter] = useState("all");
  const [verdict, setVerdict] = useState<LicenseVerdict | "all">("all");
  // (domain, family) -> earliest run it appeared in, across all reports on disk.
  const [firstSeen, setFirstSeen] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    api
      .getFirstSeen(source)
      .then((entries) =>
        setFirstSeen(
          new Map(entries.map((r) => [firstSeenKey(r.domain, r.family), r.first_seen])),
        ),
      )
      .catch(() => {
        // first-seen is a nice-to-have; ignore failures
      });
  }, [source]);

  const rows = useMemo(() => {
    return toRows(domains)
      .filter((r) => (domainFilter === "all" ? true : r.domain === domainFilter))
      .filter((r) => (verdict === "all" ? true : r.verdict === verdict));
  }, [domains, domainFilter, verdict]);

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
          <span className="mb-1 block font-medium">License</span>
          <Select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value as LicenseVerdict | "all")}
          >
            <option value="all">all</option>
            <option value="violation">violation</option>
            <option value="needs_check">needs check</option>
            <option value="ok">ok</option>
          </Select>
        </label>
      </div>

      <div className="overflow-x-auto rounded-card border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Fonts by host</caption>
          <thead>
            <tr className="bg-surface2 text-left text-muted">
              {COLUMNS.map((c) => (
                <th key={c} scope="col" className={TH}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <HostFontRow
                key={`${r.host}:${r.family}:${i}`}
                row={r}
                firstSeen={firstSeen.get(firstSeenKey(r.domain, r.family))}
              />
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-6 text-center text-muted">
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
