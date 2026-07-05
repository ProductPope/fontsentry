import { useMemo, useState } from "react";
import { PrivacyText, VerdictBadge } from "../components/Badge";
import { Select } from "../components/Select";
import { TextInput } from "../components/TextInput";
import type { Finding, LicenseVerdict } from "../lib/api";
import { cn } from "../lib/cn";
import { findingKey, groupFindings, needsAction, worstVerdict, type Group } from "../lib/findings";
import { delivery, isPrivacyFlagged } from "../lib/privacy";
import { FindingDetail } from "./finding-detail";

type Focus = "action" | "privacy" | "all";

const FOCUS_CHIPS: { id: Focus; label: string }[] = [
  { id: "action", label: "Needs action" },
  { id: "privacy", label: "Privacy (GDPR)" },
  { id: "all", label: "All" },
];

// Sort severity: most-attention-worthy first.
const RANK: Record<LicenseVerdict, number> = { violation: 2, needs_check: 1, ok: 0 };

function DeliveryBadge({ finding }: { finding: Finding }) {
  const d = delivery(finding);
  return (
    <span
      className={cn(
        "inline-block rounded-chip px-2 py-0.5 text-xs font-medium",
        d.flagged ? "bg-band-medium-bg text-band-medium" : "text-faint",
      )}
    >
      {/* Don't rely on colour/glyph alone (WCAG 1.4.1): carry the meaning in text. */}
      {d.flagged && <span className="sr-only">Third-party delivery, privacy concern: </span>}
      {d.flagged && (
        <span role="img" aria-label="warning">
          ⚠{" "}
        </span>
      )}
      {d.label}
    </span>
  );
}

// Comp table-header cell: small uppercase, faint, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [search, setSearch] = useState("");
  const [focus, setFocus] = useState<Focus>("action");
  const [verdict, setVerdict] = useState<LicenseVerdict | "all">("all");
  const [desc, setDesc] = useState(true);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return findings
      .filter((f) =>
        focus === "action" ? needsAction(f) : focus === "privacy" ? isPrivacyFlagged(f) : true,
      )
      .filter((f) => (verdict === "all" ? true : f.license_verdict === verdict))
      .filter(
        (f) =>
          q === "" ||
          f.family.toLowerCase().includes(q) ||
          (f.owner ?? "").toLowerCase().includes(q),
      )
      .sort((a, b) =>
        desc
          ? RANK[b.license_verdict] - RANK[a.license_verdict]
          : RANK[a.license_verdict] - RANK[b.license_verdict],
      );
  }, [findings, search, focus, verdict, desc]);

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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div
          role="group"
          aria-label="Filter findings"
          className="flex rounded-tk border border-stroke bg-surface2 p-0.5"
        >
          {FOCUS_CHIPS.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setFocus(c.id)}
              aria-pressed={focus === c.id}
              className={cn(
                "rounded-chip px-3 py-1 text-sm font-medium transition-colors",
                focus === c.id ? "bg-surface text-ink shadow-tk" : "text-muted hover:text-ink",
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block font-medium">Search</span>
            <TextInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="font or owner"
              aria-label="Search findings"
            />
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
          <label className="flex items-center gap-1.5 pb-2 text-sm">
            <input
              type="checkbox"
              checked={grouped}
              onChange={(e) => setGrouped(e.target.checked)}
            />
            <span className="font-medium">Group variants</span>
          </label>
        </div>
      </div>

      {focus === "action" && hiddenCount > 0 && (
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
                  onClick={() => setDesc((d) => !d)}
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
              const groupOpen = expandedGroups.has(g.key);
              return (
                <GroupRows
                  key={g.key}
                  group={g}
                  isOpen={groupOpen}
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

function GroupRows({
  group,
  isOpen,
  onToggle,
  expanded,
  onToggleFinding,
}: {
  group: Group;
  isOpen: boolean;
  onToggle: () => void;
  expanded: string | null;
  onToggleFinding: (key: string) => void;
}) {
  const verdict = worstVerdict(group.findings);
  const domains = new Set(group.findings.flatMap((f) => f.domains)).size;
  const owners = new Set(group.findings.map((f) => f.owner ?? ""));
  const owner = owners.size === 1 ? [...owners][0] || "—" : "—";
  // Representative delivery: prefer a privacy-flagged variant so the group row
  // still warns when any weight is served third-party.
  const rep = group.findings.find(isPrivacyFlagged) ?? group.findings[0]!;
  return (
    <>
      <tr className="border-t border-stroke bg-surface2/40">
        <td className="px-4 py-2">
          <button onClick={onToggle} aria-expanded={isOpen} className="text-left font-semibold">
            <span aria-hidden="true">{isOpen ? "▾ " : "▸ "}</span>
            {group.label}
            <span className="ml-2 text-xs font-normal text-faint">
              {group.findings.length} variants
            </span>
          </button>
        </td>
        <td className="px-4 py-2">{owner}</td>
        <td className="px-4 py-2">
          <DeliveryBadge finding={rep} />
        </td>
        <td className="px-4 py-2 font-mono tabular-nums">{domains}</td>
        <td className="px-4 py-2">
          <VerdictBadge verdict={verdict} />
        </td>
        <td className="px-4 py-2">
          <PrivacyText privacy={rep.privacy} />
        </td>
      </tr>
      {isOpen &&
        group.findings.map((f) => {
          const key = findingKey(f);
          return (
            <FindingRows
              key={key}
              finding={f}
              isOpen={expanded === key}
              onToggle={() => onToggleFinding(key)}
              indent
            />
          );
        })}
    </>
  );
}

function FindingRows({
  finding,
  isOpen,
  onToggle,
  indent = false,
}: {
  finding: Finding;
  isOpen: boolean;
  onToggle: () => void;
  indent?: boolean;
}) {
  const detailId = `finding-detail-${findingKey(finding)}`;
  return (
    <>
      <tr className="border-t border-stroke">
        <td className={cn("px-4 py-2", indent && "pl-9")}>
          <button
            onClick={onToggle}
            aria-expanded={isOpen}
            aria-controls={detailId}
            className={cn("text-left", indent ? "font-normal text-muted" : "font-medium")}
          >
            <span aria-hidden="true">{isOpen ? "▾ " : "▸ "}</span>
            {finding.family}
          </button>
        </td>
        <td className="px-4 py-2">{finding.owner ?? "—"}</td>
        <td className="px-4 py-2">
          <DeliveryBadge finding={finding} />
        </td>
        <td className="px-4 py-2 font-mono tabular-nums">{finding.domains.length}</td>
        <td className="px-4 py-2">
          <VerdictBadge verdict={finding.license_verdict} />
        </td>
        <td className="px-4 py-2">
          <PrivacyText privacy={finding.privacy} />
        </td>
      </tr>
      {isOpen && (
        <tr id={detailId}>
          <td colSpan={6} className="p-0">
            <FindingDetail finding={finding} />
          </td>
        </tr>
      )}
    </>
  );
}
