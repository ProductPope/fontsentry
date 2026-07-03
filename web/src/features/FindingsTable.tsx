import { useEffect, useMemo, useState } from "react";
import { RiskBadge, StatusText } from "../components/Badge";
import { Select } from "../components/Select";
import { TextInput } from "../components/TextInput";
import { cn } from "../lib/cn";
import { api } from "../lib/api";
import type { Band, Finding, Status } from "../lib/api";
import { delivery, isPrivacyFlagged, needsAction, privacyAdvice } from "../lib/privacy";
import { safeHref } from "../lib/url";

type Focus = "action" | "privacy" | "all";

const FOCUS_CHIPS: { id: Focus; label: string }[] = [
  { id: "action", label: "Needs action" },
  { id: "privacy", label: "Privacy (GDPR)" },
  { id: "all", label: "All" },
];

function DeliveryBadge({ finding }: { finding: Finding }) {
  const d = delivery(finding);
  return (
    <span
      className={cn(
        "inline-block rounded-chip px-2 py-0.5 text-xs font-medium",
        d.flagged ? "bg-band-medium-bg text-band-medium" : "text-faint",
      )}
    >
      {d.flagged ? "⚠ " : ""}
      {d.label}
    </span>
  );
}

// Comp table-header cell: small uppercase, faint, wide tracking.
const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

const BAND_TEXT: Record<Band, string> = {
  high: "text-band-high",
  medium: "text-band-medium",
  low: "text-band-low",
};

const BAND_ORDER: Record<Band, number> = { low: 0, medium: 1, high: 2 };

interface Group {
  key: string;
  label: string;
  findings: Finding[];
}

function groupKeyOf(f: Finding): string {
  return (f.family_group || f.family).toLowerCase().replace(/[^a-z0-9]/g, "");
}

function worstBand(findings: Finding[]): Band {
  return findings.reduce<Band>(
    (worst, f) => (BAND_ORDER[f.band] > BAND_ORDER[worst] ? f.band : worst),
    "low",
  );
}

type Thresholds = { medium: number; high: number } | null;
type RuleInfo = { id: string; description: string };

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

// A 0-100 gauge with the risk bands as coloured zones and a marker at the score.
function ScoreGauge({ score, band, thresholds }: { score: number; band: Band; thresholds: Thresholds }) {
  const pos = Math.min(100, Math.max(0, score));
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className={cn("font-mono text-3xl font-bold tabular-nums", BAND_TEXT[band])}>
          {score}
        </span>
        <span className="text-xs text-faint">/ 100 · {band} risk</span>
      </div>
      <div className="relative mt-2 h-2 w-full max-w-md rounded-full">
        {thresholds ? (
          <div className="flex h-full w-full overflow-hidden rounded-full">
            <div className="h-full bg-band-low-bg" style={{ width: `${thresholds.medium}%` }} />
            <div
              className="h-full bg-band-medium-bg"
              style={{ width: `${Math.max(0, thresholds.high - thresholds.medium)}%` }}
            />
            <div className="h-full bg-band-high-bg" style={{ width: `${Math.max(0, 100 - thresholds.high)}%` }} />
          </div>
        ) : (
          <div className="h-full w-full rounded-full bg-sunken" />
        )}
        <span
          className="absolute top-[-2px] h-3 w-0.5 bg-ink"
          style={{ left: `${pos}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  );
}

function FindingDetail({
  finding,
  thresholds,
  rules,
}: {
  finding: Finding;
  thresholds: Thresholds;
  rules: RuleInfo[] | null;
}) {
  const m = finding.metadata;
  const resolved = finding.status === "resolved";
  const firedIds = new Set(finding.triggered_rules.map((r) => r.id));
  const didNotApply = (rules ?? []).filter((r) => !firedIds.has(r.id));
  const advice = privacyAdvice(finding);

  return (
    <div className="space-y-5 bg-surface2 px-4 py-4 text-sm">
      <ScoreGauge score={finding.score} band={finding.band} thresholds={thresholds} />

      {advice && (
        <p className="rounded-tk border-l-2 border-band-medium bg-surface px-3 py-2 text-xs text-muted">
          <strong className="text-band-medium">Delivery: {delivery(finding).label}.</strong>{" "}
          {advice}
        </p>
      )}

      {!finding.applied && (
        <p className="rounded-tk bg-surface px-3 py-2 text-xs text-muted">
          <strong>Served but not applied.</strong> This font file is hosted on the site (via
          <code className="mx-1 font-mono">@font-face</code>) but no text on the page renders in it,
          so the score is lowered. Hosting the file can still be a licensing concern.
        </p>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
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
            {finding.example_urls.length > 0 && (
              <div className="mt-1 text-xs text-muted">
                Seen on {finding.page_count} page{finding.page_count === 1 ? "" : "s"}, e.g.:
                <ul className="mt-0.5 space-y-0.5">
                  {finding.example_urls.map((u) =>
                    safeHref(u) ? (
                      <li key={u}>
                        <a
                          href={safeHref(u) ?? undefined}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono break-all text-accent underline"
                        >
                          {u}
                        </a>
                      </li>
                    ) : (
                      <li key={u} className="font-mono break-all">
                        {u}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            )}
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Font details</h3>
            <dl className="space-y-1">
              <Row label="Designer" value={m?.designer ?? "—"} />
              <Row label="Copyright" value={m?.copyright ?? "—"} />
              <Row label="License" value={m?.license_description ?? "—"} />
              <Row label="License URL" value={m?.license_url ?? "—"} />
              <Row label="Unique ID" value={m?.unique_id ?? "—"} />
              <Row label="Glyphs" value={m?.num_glyphs != null ? String(m.num_glyphs) : "—"} />
            </dl>
          </div>
        </div>
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer font-semibold text-muted">
          How the score was reached
        </summary>
        <div className="mt-2 grid gap-4 sm:grid-cols-2">
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-faint">Rules that fired</div>
            {finding.triggered_rules.length > 0 ? (
              <ul className="space-y-1">
                {finding.triggered_rules.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3">
                    <span>{r.description || r.id}</span>
                    <span className="shrink-0 font-mono text-muted">+{Math.round(r.points)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">None.</p>
            )}
          </div>
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-faint">Didn't apply</div>
            {rules === null ? (
              <p className="text-faint">—</p>
            ) : didNotApply.length > 0 ? (
              <ul className="space-y-1 text-faint">
                {didNotApply.map((r) => (
                  <li key={r.id}>{r.description || r.id}</li>
                ))}
              </ul>
            ) : (
              <p className="text-faint">Every rule fired.</p>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-24 shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  );
}

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [search, setSearch] = useState("");
  const [focus, setFocus] = useState<Focus>("action");
  const [status, setStatus] = useState<Status | "all">("all");
  const [desc, setDesc] = useState(true);
  const [grouped, setGrouped] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Band thresholds + the full rule list power the score gauge and the
  // "didn't apply" breakdown. Best-effort — the panel degrades without them.
  const [thresholds, setThresholds] = useState<Thresholds>(null);
  const [rules, setRules] = useState<RuleInfo[] | null>(null);
  useEffect(() => {
    api
      .getRules()
      .then((cfg) => {
        setThresholds(cfg.scoring.bands);
        setRules(cfg.rules.map((r) => ({ id: r.id, description: r.description })));
      })
      .catch(() => {
        // gauge/breakdown are enhancements; ignore failures
      });
  }, []);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return findings
      .filter((f) =>
        focus === "action" ? needsAction(f) : focus === "privacy" ? isPrivacyFlagged(f) : true,
      )
      .filter((f) => (status === "all" ? true : f.status === status))
      .filter(
        (f) =>
          q === "" ||
          f.family.toLowerCase().includes(q) ||
          (f.owner ?? "").toLowerCase().includes(q),
      )
      .sort((a, b) => (desc ? b.score - a.score : a.score - b.score));
  }, [findings, search, focus, status, desc]);

  const hiddenCount = findings.length - rows.length;

  const groups = useMemo(() => {
    const map = new Map<string, Group>();
    for (const f of rows) {
      const key = groupKeyOf(f);
      const g = map.get(key);
      if (g) g.findings.push(f);
      else map.set(key, { key, label: f.family_group || f.family, findings: [f] });
    }
    const scoreOf = (g: Group) => Math.max(...g.findings.map((f) => f.score));
    return [...map.values()].sort((a, b) => (desc ? scoreOf(b) - scoreOf(a) : scoreOf(a) - scoreOf(b)));
  }, [rows, desc]);

  const toggleGroup = (key: string) =>
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <section aria-label="Findings" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex rounded-tk border border-stroke bg-surface2 p-0.5">
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
            <span className="mb-1 block font-medium">Status</span>
            <Select value={status} onChange={(e) => setStatus(e.target.value as Status | "all")}>
              <option value="all">all</option>
              <option value="open">open</option>
              <option value="resolved">resolved</option>
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
          {hiddenCount} open-licensed / low-risk font{hiddenCount === 1 ? "" : "s"} hidden — switch
          to <strong>All</strong> to see everything.
        </p>
      )}

      <div className="overflow-x-auto rounded-card border border-stroke">
        <table className="w-full border-collapse bg-surface text-sm">
          <caption className="sr-only">Detected fonts and their risk</caption>
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
            {(grouped ? groups : rows.map((f) => ({ key: findingKey(f), label: f.family, findings: [f] }))).map(
              (g) => {
                // A single-variant group renders as a plain row — only families
                // that actually split into weights/styles get a group header.
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
                      thresholds={thresholds}
                      rules={rules}
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
                    thresholds={thresholds}
                    rules={rules}
                  />
                );
              },
            )}
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

function GroupRows({
  group,
  isOpen,
  onToggle,
  expanded,
  onToggleFinding,
  thresholds,
  rules,
}: {
  group: Group;
  isOpen: boolean;
  onToggle: () => void;
  expanded: string | null;
  onToggleFinding: (key: string) => void;
  thresholds: Thresholds;
  rules: RuleInfo[] | null;
}) {
  const band = worstBand(group.findings);
  const maxScore = Math.max(...group.findings.map((f) => f.score));
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
            {isOpen ? "▾ " : "▸ "}
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
        <td className="px-4 py-2 font-mono font-semibold tabular-nums">{maxScore}</td>
        <td className="px-4 py-2">
          <RiskBadge band={band} />
        </td>
        <td className="px-4 py-2" />
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
              thresholds={thresholds}
              rules={rules}
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
  thresholds,
  rules,
  indent = false,
}: {
  finding: Finding;
  isOpen: boolean;
  onToggle: () => void;
  thresholds: Thresholds;
  rules: RuleInfo[] | null;
  indent?: boolean;
}) {
  return (
    <>
      <tr className="border-t border-stroke">
        <td className={cn("px-4 py-2", indent && "pl-9")}>
          <button
            onClick={onToggle}
            aria-expanded={isOpen}
            className={cn("text-left", indent ? "font-normal text-muted" : "font-medium")}
          >
            {isOpen ? "▾ " : "▸ "}
            {finding.family}
          </button>
        </td>
        <td className="px-4 py-2">{finding.owner ?? "—"}</td>
        <td className="px-4 py-2">
          <DeliveryBadge finding={finding} />
        </td>
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
            <FindingDetail finding={finding} thresholds={thresholds} rules={rules} />
          </td>
        </tr>
      )}
    </>
  );
}
