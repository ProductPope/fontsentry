import { useEffect, useMemo, useState } from "react";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { Sparkline } from "../components/Sparkline";
import { Spinner } from "../components/Spinner";
import { Tabs } from "../components/Tabs";
import { cn } from "../lib/cn";
import { DomainsView } from "./DomainsView";
import { FindingsTable } from "./FindingsTable";
import { GettingStarted } from "./GettingStarted";
import { api } from "../lib/api";
import type { DiffResult, LicenseVerdict, RunMeta, RunReport } from "../lib/api";
import { isPrivacyFlagged } from "../lib/privacy";

export type View = "fonts" | "domains";

const TABS = [
  { id: "fonts", label: "Fonts" },
  { id: "domains", label: "Domains" },
];

const VERDICT_TONE: Record<LicenseVerdict, string> = {
  violation: "text-band-high",
  needs_check: "text-band-medium",
  ok: "text-band-low",
};

type VerdictCounts = Record<LicenseVerdict, number>;

function countByVerdict(report: RunReport): VerdictCounts {
  const counts: VerdictCounts = { violation: 0, needs_check: 0, ok: 0 };
  for (const f of report.findings) counts[f.license_verdict] += 1;
  return counts;
}

function deltaText(d: number): string {
  if (d > 0) return `↑${d}`;
  if (d < 0) return `↓${-d}`;
  return "±0";
}

interface OverviewScreenProps {
  runs: RunMeta[];
  selectedId: string;
  onSelect: (id: string) => void;
  report: RunReport | null;
  loading: boolean;
  view: View;
  onView: (view: View) => void;
  source: "real" | "demo";
  onSource: (source: "real" | "demo") => void;
}

const SOURCES: { id: "real" | "demo"; label: string }[] = [
  { id: "real", label: "Your data" },
  { id: "demo", label: "Demo data" },
];

export function OverviewScreen({
  runs,
  selectedId,
  onSelect,
  report,
  loading,
  view,
  onView,
  source,
  onSource,
}: OverviewScreenProps) {
  // Previous run (chronologically before the selected one) for "vs last run"
  // deltas. runs are newest-first, so the previous run is the next index.
  const [prev, setPrev] = useState<{ byVerdict: VerdictCounts } | null>(null);

  useEffect(() => {
    const i = runs.findIndex((r) => r.id === selectedId);
    const prevId = i >= 0 ? runs[i + 1]?.id : undefined;
    if (!prevId) {
      setPrev(null);
      return;
    }
    let cancelled = false;
    api
      .getRun(prevId, source)
      .then((rep) => {
        if (cancelled) return;
        setPrev({ byVerdict: countByVerdict(rep) });
      })
      .catch(() => setPrev(null));
    return () => {
      cancelled = true;
    };
  }, [runs, selectedId, source]);

  // Per-finding changes vs the previous run (only when one exists).
  const [diff, setDiff] = useState<DiffResult | null>(null);
  useEffect(() => {
    const i = runs.findIndex((r) => r.id === selectedId);
    if (i < 0 || i >= runs.length - 1) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    api
      .getRunDiff(selectedId, source)
      .then((d) => {
        if (!cancelled) setDiff(d);
      })
      .catch(() => setDiff(null));
    return () => {
      cancelled = true;
    };
  }, [runs, selectedId, source]);

  const stats = useMemo(() => {
    if (report === null) return null;
    const byVerdict = countByVerdict(report);
    const domains = report.domains.length;
    const live = report.domains.filter((d) => d.is_live).length;
    const clean = report.domains.filter((d) =>
      d.fonts.every((f) => f.license_verdict === "ok"),
    ).length;
    const privacyFlagged = report.findings.filter(isPrivacyFlagged).length;
    return { byVerdict, domains, live, unreachable: domains - live, clean, privacyFlagged };
  }, [report]);

  // Trend of findings needing action across every run, oldest → newest.
  const trend = useMemo(() => [...runs].reverse().map((r) => r.summary.needs_action), [runs]);

  const sourceToggle = (
    <div role="group" aria-label="Data source" className="flex rounded-tk border border-stroke bg-surface2 p-0.5">
      {SOURCES.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSource(s.id)}
          aria-pressed={source === s.id}
          className={cn(
            "rounded-chip px-3 py-1 text-sm font-medium transition-colors",
            source === s.id ? "bg-surface text-ink shadow-tk" : "text-muted hover:text-ink",
          )}
        >
          {s.label}
        </button>
      ))}
    </div>
  );

  if (runs.length === 0) {
    return (
      <div className="space-y-5">
        <div className="flex justify-end">{sourceToggle}</div>
        {source === "demo" ? (
          <Card>
            <p className="text-sm text-muted">
              No demo audits yet. Run an audit on demo data to see results here.
            </p>
          </Card>
        ) : (
          <GettingStarted />
        )}
      </div>
    );
  }

  const currentOpen = stats ? stats.byVerdict.violation + stats.byVerdict.needs_check : 0;
  const prevOpen = prev ? prev.byVerdict.violation + prev.byVerdict.needs_check : null;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">{sourceToggle}</div>
      <div className="flex items-end gap-2">
        <label className="block flex-1 text-sm">
          <span className="mb-1 block font-medium">Run</span>
          <Select
            value={selectedId}
            onChange={(e) => onSelect(e.target.value)}
            className="font-mono text-xs"
          >
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id}
              </option>
            ))}
          </Select>
        </label>
        <a
          href={api.exportCsvUrl(selectedId, source)}
          download
          className="rounded-tk border border-stroke bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-canvas"
        >
          Export CSV
        </a>
      </div>

      {stats && (
        <>
          {stats.privacyFlagged > 0 && (
            <div className="rounded-card border-l-4 border-band-medium bg-band-medium-bg/40 px-4 py-3 text-sm">
              <span className="font-semibold text-band-medium">⚠ Privacy (GDPR/RODO): </span>
              {stats.privacyFlagged} font{stats.privacyFlagged === 1 ? "" : "s"} load from third
              parties (e.g. the Google Fonts API), sending visitor IPs off-site. Self-host them to
              stay compliant — open the <strong>Privacy (GDPR)</strong> filter under Fonts for the
              list and the fix.
            </div>
          )}

          <div className="text-xs font-semibold uppercase tracking-wide text-faint">
            License risk
          </div>
          <h2 className="sr-only">Risk posture</h2>
          <section aria-label="Risk posture" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Posture
              label="Violation"
              count={stats.byVerdict.violation}
              tone={VERDICT_TONE.violation}
              delta={prev ? stats.byVerdict.violation - prev.byVerdict.violation : undefined}
            />
            <Posture
              label="Need check"
              count={stats.byVerdict.needs_check}
              tone={VERDICT_TONE.needs_check}
              delta={prev ? stats.byVerdict.needs_check - prev.byVerdict.needs_check : undefined}
            />
            <Posture
              label="OK"
              count={stats.byVerdict.ok}
              tone={VERDICT_TONE.ok}
              delta={prev ? stats.byVerdict.ok - prev.byVerdict.ok : undefined}
            />
            <Posture
              label="Privacy"
              count={stats.privacyFlagged}
              tone="text-band-medium"
            />
          </section>

          <div className="grid gap-3 sm:grid-cols-2">
            <Card>
              <div className="mb-2 text-xs uppercase tracking-wide text-faint">Portfolio</div>
              <div className="grid grid-cols-2 gap-3">
                <Sub label="Domains" value={stats.domains} />
                <Sub label="Live" value={stats.live} />
                <Sub label="Unreachable" value={stats.unreachable} />
                <Sub label="Clean" value={stats.clean} />
              </div>
            </Card>

            {trend.length >= 2 && (
              <Card>
                <div className="text-xs uppercase tracking-wide text-faint">
                  Active findings over time
                </div>
                <div className="mt-2 flex items-end justify-between gap-4">
                  <div>
                    <span className="font-mono text-2xl font-bold tabular-nums">{currentOpen}</span>
                    {prevOpen !== null && (
                      <span className="ml-2 text-xs text-faint">
                        {deltaText(currentOpen - prevOpen)} vs last run
                      </span>
                    )}
                  </div>
                  <Sparkline
                    values={trend}
                    label={`Active findings across the last ${trend.length} audits`}
                  />
                </div>
              </Card>
            )}
          </div>
        </>
      )}

      {diff && (
        <Card>
          <div className="text-xs uppercase tracking-wide text-faint">Changes since last run</div>
          {diff.new_findings.length || diff.resolved_findings.length || diff.changed.length ? (
            <div className="mt-2 space-y-2 text-sm">
              {diff.new_findings.length > 0 && (
                <ChangeRow
                  tone="text-band-high"
                  label="New"
                  items={diff.new_findings.map((f) => f.family)}
                />
              )}
              {diff.resolved_findings.length > 0 && (
                <ChangeRow
                  tone="text-band-low"
                  label="Resolved"
                  items={diff.resolved_findings.map((f) => f.family)}
                />
              )}
              {diff.changed.length > 0 && (
                <ChangeRow
                  tone="text-band-medium"
                  label="Changed"
                  items={diff.changed.map((c) => `${c.family} (${c.old_verdict}→${c.new_verdict})`)}
                />
              )}
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted">No changes since the last run.</p>
          )}
        </Card>
      )}

      <Tabs tabs={TABS} active={view} onChange={(id) => onView(id as View)} />

      {loading && <Spinner label="Loading report…" />}

      {report && view === "fonts" && <FindingsTable findings={report.findings} />}
      {report && view === "domains" && (
        <DomainsView domains={report.domains} source={source} />
      )}
    </div>
  );
}

// Active (open) finding count for a risk band, with an optional "vs last run"
// delta. Suppressed reuses the same card with a muted tone.
function Posture({
  label,
  count,
  tone,
  delta,
}: {
  label: string;
  count: number;
  tone: string;
  delta?: number;
}) {
  return (
    <Card>
      <div className={cn("font-mono text-2xl font-bold tabular-nums", tone)}>{count}</div>
      <div className="text-xs uppercase tracking-wide text-faint">{label}</div>
      {delta !== undefined && (
        <div className="mt-0.5 font-mono text-xs text-faint">{deltaText(delta)} vs last</div>
      )}
    </Card>
  );
}

function ChangeRow({ tone, label, items }: { tone: string; label: string; items: string[] }) {
  return (
    <div>
      <span className={cn("font-medium", tone)}>
        {label} ({items.length})
      </span>{" "}
      <span className="text-muted">{items.join(", ")}</span>
    </div>
  );
}

function Sub({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-mono text-xl font-bold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}
