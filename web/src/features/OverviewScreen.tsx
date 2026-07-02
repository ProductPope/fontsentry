import { useEffect, useMemo, useState } from "react";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { Sparkline } from "../components/Sparkline";
import { Spinner } from "../components/Spinner";
import { Tabs } from "../components/Tabs";
import { cn } from "../lib/cn";
import { DomainsView } from "./DomainsView";
import { Faq } from "./Faq";
import { FindingsTable } from "./FindingsTable";
import { GettingStarted } from "./GettingStarted";
import { api } from "../lib/api";
import type { Band, DiffResult, RunMeta, RunReport } from "../lib/api";

export type View = "fonts" | "domains";

const TABS = [
  { id: "fonts", label: "Fonts" },
  { id: "domains", label: "Domains" },
];

const BAND_TONE: Record<Band, string> = {
  high: "text-band-high",
  medium: "text-band-medium",
  low: "text-band-low",
};

function openByBand(report: RunReport): Record<Band, number> {
  const byBand: Record<Band, number> = { high: 0, medium: 0, low: 0 };
  for (const f of report.findings) if (f.status === "open") byBand[f.band] += 1;
  return byBand;
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
}

export function OverviewScreen({
  runs,
  selectedId,
  onSelect,
  report,
  loading,
  view,
  onView,
}: OverviewScreenProps) {
  // Previous run (chronologically before the selected one) for "vs last run"
  // deltas. runs are newest-first, so the previous run is the next index.
  const [prev, setPrev] = useState<{ byBand: Record<Band, number>; suppressed: number } | null>(
    null,
  );

  useEffect(() => {
    const i = runs.findIndex((r) => r.id === selectedId);
    const prevId = i >= 0 ? runs[i + 1]?.id : undefined;
    if (!prevId) {
      setPrev(null);
      return;
    }
    let cancelled = false;
    api
      .getRun(prevId)
      .then((rep) => {
        if (cancelled) return;
        setPrev({
          byBand: openByBand(rep),
          suppressed: rep.findings.filter((f) => f.status === "resolved").length,
        });
      })
      .catch(() => setPrev(null));
    return () => {
      cancelled = true;
    };
  }, [runs, selectedId]);

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
      .getRunDiff(selectedId)
      .then((d) => {
        if (!cancelled) setDiff(d);
      })
      .catch(() => setDiff(null));
    return () => {
      cancelled = true;
    };
  }, [runs, selectedId]);

  const stats = useMemo(() => {
    if (report === null) return null;
    const byBand = openByBand(report);
    const suppressed = report.findings.filter((f) => f.status === "resolved").length;
    const domains = report.domains.length;
    const live = report.domains.filter((d) => d.is_live).length;
    const clean = report.domains.filter((d) => d.fonts.every((f) => f.status !== "open")).length;
    return { byBand, suppressed, domains, live, unreachable: domains - live, clean };
  }, [report]);

  // Trend of active (open) findings across every run, oldest → newest.
  const trend = useMemo(() => [...runs].reverse().map((r) => r.summary.open_findings), [runs]);

  if (runs.length === 0) {
    return <GettingStarted />;
  }

  const currentOpen = stats ? stats.byBand.high + stats.byBand.medium + stats.byBand.low : 0;
  const prevOpen = prev ? prev.byBand.high + prev.byBand.medium + prev.byBand.low : null;

  return (
    <div className="space-y-5">
      <label className="block text-sm">
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

      {stats && (
        <>
          <section aria-label="Risk posture" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Posture
              label="High"
              count={stats.byBand.high}
              tone={BAND_TONE.high}
              delta={prev ? stats.byBand.high - prev.byBand.high : undefined}
            />
            <Posture
              label="Medium"
              count={stats.byBand.medium}
              tone={BAND_TONE.medium}
              delta={prev ? stats.byBand.medium - prev.byBand.medium : undefined}
            />
            <Posture
              label="Low"
              count={stats.byBand.low}
              tone={BAND_TONE.low}
              delta={prev ? stats.byBand.low - prev.byBand.low : undefined}
            />
            <Posture
              label="Suppressed"
              count={stats.suppressed}
              tone="text-muted"
              delta={prev ? stats.suppressed - prev.suppressed : undefined}
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
                  items={diff.changed.map((c) => `${c.family} (${c.old_score}→${c.new_score})`)}
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
      {report && view === "domains" && <DomainsView domains={report.domains} />}

      <Faq />
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
