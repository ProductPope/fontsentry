import { useMemo, useState } from "react";
import { RiskBadge, StatusText } from "../components/Badge";
import { Select } from "../components/Select";
import { TextInput } from "../components/TextInput";
import type { Band, Finding, Status } from "../lib/api";

// Comp table-header cell: small uppercase, faint, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

function findingKey(f: Finding): string {
  return `${f.family}::${f.owner ?? ""}`;
}

function isSystemOnly(f: Finding): boolean {
  return f.embeddings.length > 0 && f.embeddings.every((e) => e === "system");
}

// Plain-language next step for a non-technical operator.
function actionText(f: Finding): string {
  if (f.status === "resolved") {
    return "No action needed — a matching license in your Registry already covers this.";
  }
  if (isSystemOnly(f)) {
    return "This is a system / fallback font (not embedded on the page). Usually nothing to do.";
  }
  return (
    "If you own a license that permits this use, add it under Registry — the same owner and " +
    "font family, plus the domains it covers. On the next scan this clears automatically."
  );
}

function FindingDetail({ finding }: { finding: Finding }) {
  const m = finding.metadata;
  const resolved = finding.status === "resolved";
  return (
    <div className="grid gap-5 bg-surface2 px-4 py-4 text-sm sm:grid-cols-2">
      <div className="space-y-4">
        <div>
          <h3 className="mb-1 font-semibold">{resolved ? "Why it's cleared" : "Why it's flagged"}</h3>
          {resolved ? (
            <p className="text-band-low">
              {finding.suppression_reason ?? "Covered by a license in your registry."}
            </p>
          ) : finding.triggered_rules.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-muted">
              {finding.triggered_rules.map((r) => (
                <li key={r.id}>{r.description || r.id}</li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">No specific reasons recorded.</p>
          )}
        </div>
        <div>
          <h3 className="mb-1 font-semibold">What you can do</h3>
          <p className="text-muted">{actionText(finding)}</p>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="mb-1 font-semibold">Where it appears</h3>
          <p className="font-mono text-xs break-words text-muted">
            {finding.domains.join(", ") || "—"}
          </p>
        </div>
        <div>
          <h3 className="mb-1 font-semibold">Font details</h3>
          <dl className="space-y-1">
            <Row label="Designer" value={m?.designer ?? "—"} />
            <Row label="Copyright" value={m?.copyright ?? "—"} />
            <Row label="License" value={m?.license_description ?? "—"} />
          </dl>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-24 shrink-0 text-muted">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [search, setSearch] = useState("");
  const [band, setBand] = useState<Band | "all">("all");
  const [status, setStatus] = useState<Status | "all">("all");
  const [desc, setDesc] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return findings
      .filter((f) => (band === "all" ? true : f.band === band))
      .filter((f) => (status === "all" ? true : f.status === status))
      .filter(
        (f) =>
          q === "" ||
          f.family.toLowerCase().includes(q) ||
          (f.owner ?? "").toLowerCase().includes(q),
      )
      .sort((a, b) => (desc ? b.score - a.score : a.score - b.score));
  }, [findings, search, band, status, desc]);

  return (
    <section aria-label="Findings" className="space-y-3">
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
          <span className="mb-1 block font-medium">Band</span>
          <Select value={band} onChange={(e) => setBand(e.target.value as Band | "all")}>
            <option value="all">all</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </Select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Status</span>
          <Select value={status} onChange={(e) => setStatus(e.target.value as Status | "all")}>
            <option value="all">all</option>
            <option value="open">open</option>
            <option value="resolved">resolved</option>
          </Select>
        </label>
      </div>

      <div className="overflow-x-auto rounded-card border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Detected fonts and their risk</caption>
          <thead>
            <tr className="bg-surface2 text-left text-faint">
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
                Domains
              </th>
              <th scope="col" className={TH}>
                <button
                  onClick={() => setDesc((d) => !d)}
                  aria-label={`Sort by score ${desc ? "ascending" : "descending"}`}
                >
                  Score {desc ? "▼" : "▲"}
                </button>
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
            {rows.map((f) => {
              const key = findingKey(f);
              const isOpen = expanded === key;
              return (
                <FindingRows key={key} finding={f} isOpen={isOpen} onToggle={() =>
                  setExpanded(isOpen ? null : key)
                } />
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted">
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

function FindingRows({
  finding,
  isOpen,
  onToggle,
}: {
  finding: Finding;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="border-t border-stroke">
        <td className="px-4 py-2">
          <button onClick={onToggle} aria-expanded={isOpen} className="text-left font-medium">
            {isOpen ? "▾ " : "▸ "}
            {finding.family}
          </button>
        </td>
        <td className="px-4 py-2">{finding.owner ?? "—"}</td>
        <td className="px-4 py-2 font-mono text-xs">{finding.embeddings.join(", ") || "—"}</td>
        <td className="px-4 py-2 font-mono tabular-nums">{finding.domains.length}</td>
        <td className="px-4 py-2 font-mono font-semibold tabular-nums">{finding.score}</td>
        <td className="px-4 py-2">
          <RiskBadge band={finding.band} />
        </td>
        <td className="px-4 py-2">
          <StatusText status={finding.status} />
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={7} className="p-0">
            <FindingDetail finding={finding} />
          </td>
        </tr>
      )}
    </>
  );
}
