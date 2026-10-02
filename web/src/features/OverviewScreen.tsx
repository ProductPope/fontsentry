import { useMemo } from "react";
import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";
import { Tabs } from "../components/Tabs";
import { DomainsView } from "./DomainsView";
import { FindingsTable } from "./FindingsTable";
import { GettingStarted } from "./GettingStarted";
import { RiskPosture } from "./RiskPosture";
import { RunChanges } from "./RunChanges";
import { SourceToggle } from "./SourceToggle";
import { api } from "../lib/api";
import type { RunMeta, RunReport } from "../lib/api";
import { overviewStats } from "../lib/overview";
import { useRunComparison } from "../lib/useRunComparison";

export type View = "fonts" | "domains";

const TABS = [
  { id: "fonts", label: "Fonts" },
  { id: "domains", label: "Domains" },
];

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
  const { prev, diff } = useRunComparison(runs, selectedId, source);
  const stats = useMemo(() => (report ? overviewStats(report) : null), [report]);
  // Trend of findings needing action across every run, oldest → newest.
  const trend = useMemo(() => [...runs].reverse().map((r) => r.summary.needs_action), [runs]);

  const sourceToggle = (
    <div className="flex justify-end">
      <SourceToggle source={source} onSource={onSource} />
    </div>
  );

  if (runs.length === 0) {
    return (
      <div className="space-y-5">
        {sourceToggle}
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

  return (
    <div className="space-y-5">
      {sourceToggle}
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

      {stats && <RiskPosture stats={stats} prev={prev} trend={trend} />}
      {diff && <RunChanges diff={diff} />}

      <Tabs tabs={TABS} active={view} onChange={(id) => onView(id as View)} />

      {loading && <Spinner label="Loading report…" />}

      {report && view === "fonts" && <FindingsTable findings={report.findings} />}
      {report && view === "domains" && <DomainsView domains={report.domains} source={source} />}
    </div>
  );
}
