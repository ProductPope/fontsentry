import { useMemo, useState } from "react";
import type { Finding } from "../lib/api";
import { filterFindings, findingKey, groupFindings } from "../lib/findings";
import type { FindingFilters } from "../lib/findings";
import { FindingRows, GroupRows } from "./FindingRows";
import { FindingsFilters } from "./FindingsFilters";

// Comp table-header cell: small uppercase, faint, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [filters, setFilters] = useState<FindingFilters>({
    focus: "action",
    verdict: "all",
    search: "",
    desc: true,
  });
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const { desc } = filters;

  const rows = useMemo(() => filterFindings(findings, filters), [findings, filters]);
  const hiddenCount = findings.length - rows.length;
  const groups = useMemo(() => groupFindings(rows, desc), [rows, desc]);

  const toggleGroup = (key: string) =>
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <section aria-labelledby="findings-heading" className="space-y-3">
      <h2 id="findings-heading" className="sr-only">
        Findings
      </h2>
      <FindingsFilters
        filters={filters}
        onChange={setFilters}
        grouped={grouped}
        onGrouped={setGrouped}
      />

      {filters.focus === "action" && hiddenCount > 0 && (
        <p className="text-xs text-faint">
          {hiddenCount} OK / no-action font{hiddenCount === 1 ? "" : "s"} hidden — switch to{" "}
          <strong>All</strong> to see everything.
        </p>
      )}

      <div className="overflow-x-auto rounded-card border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Detected fonts and their verdicts</caption>
          <thead>
            <tr className="bg-surface2 text-left text-muted">
              <th scope="col" className={TH}>
                Font
              </th>
              <th scope="col" className={TH}>
                Owner
              </th>
              <th scope="col" className={TH}>
                Delivery
              </th>
              <th scope="col" className={TH}>
                Domains
              </th>
              <th scope="col" className={TH} aria-sort={desc ? "descending" : "ascending"}>
                <button
                  onClick={() => setFilters({ ...filters, desc: !desc })}
                  aria-label={`Sort by severity ${desc ? "ascending" : "descending"}`}
                >
                  License <span aria-hidden="true">{desc ? "▼" : "▲"}</span>
                </button>
              </th>
              <th scope="col" className={TH}>
                Privacy
              </th>
            </tr>
          </thead>
          <tbody>
            {(grouped
              ? groups
              : rows.map((f) => ({ key: findingKey(f), label: f.family, findings: [f] }))
            ).map((g) => {
              // A single-variant group renders as a plain row — only families that
              // actually split into weights/styles get a group header.
              if (g.findings.length === 1) {
                const f = g.findings[0]!;
                const key = findingKey(f);
                const isOpen = expanded === key;
                return (
                  <FindingRows
                    key={key}
                    finding={f}
                    isOpen={isOpen}
                    onToggle={() => setExpanded(isOpen ? null : key)}
                  />
                );
              }
              return (
                <GroupRows
                  key={g.key}
                  group={g}
                  isOpen={expandedGroups.has(g.key)}
                  onToggle={() => toggleGroup(g.key)}
                  expanded={expanded}
                  onToggleFinding={(k) => setExpanded(expanded === k ? null : k)}
                />
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">
                  No findings match the filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
