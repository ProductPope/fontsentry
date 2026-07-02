import { useMemo } from "react";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";
import { Tabs } from "../components/Tabs";
import { cn } from "../lib/cn";
import { DomainsView } from "./DomainsView";
import { Faq } from "./Faq";
import { FindingsTable } from "./FindingsTable";
import { GettingStarted } from "./GettingStarted";
import type { Band, RunMeta, RunReport } from "../lib/api";

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
  const stats = useMemo(() => {
    if (report === null) return null;
    const open = report.findings.filter((f) => f.status === "open");
    const byBand: Record<Band, number> = { high: 0, medium: 0, low: 0 };
    for (const f of open) byBand[f.band] += 1;
    const suppressed = report.findings.filter((f) => f.status === "resolved").length;
    const domains = report.domains.length;
    const live = report.domains.filter((d) => d.is_live).length;
    const clean = report.domains.filter((d) => d.fonts.every((f) => f.status !== "open")).length;
    return { byBand, suppressed, domains, live, unreachable: domains - live, clean };
  }, [report]);

  if (runs.length === 0) {
    return <GettingStarted />;
  }

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
            <Posture label="High" count={stats.byBand.high} tone={BAND_TONE.high} />
            <Posture label="Medium" count={stats.byBand.medium} tone={BAND_TONE.medium} />
            <Posture label="Low" count={stats.byBand.low} tone={BAND_TONE.low} />
            <Posture label="Suppressed" count={stats.suppressed} tone="text-muted" />
          </section>

          <Card>
            <div className="mb-2 text-xs uppercase tracking-wide text-faint">Portfolio</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Sub label="Domains" value={stats.domains} />
              <Sub label="Live" value={stats.live} />
              <Sub label="Unreachable" value={stats.unreachable} />
              <Sub label="Clean" value={stats.clean} />
            </div>
          </Card>
        </>
      )}

      <Tabs tabs={TABS} active={view} onChange={(id) => onView(id as View)} />

      {loading && <Spinner label="Loading report…" />}

      {report && view === "fonts" && <FindingsTable findings={report.findings} />}
      {report && view === "domains" && <DomainsView domains={report.domains} />}

      <Faq />
    </div>
  );
}

// Active (open) finding count for a risk band; suppressed reuses the same card
// with a muted tone.
function Posture({ label, count, tone }: { label: string; count: number; tone: string }) {
  return (
    <Card>
      <div className={cn("font-mono text-2xl font-bold tabular-nums", tone)}>{count}</div>
      <div className="text-xs uppercase tracking-wide text-faint">{label}</div>
    </Card>
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
