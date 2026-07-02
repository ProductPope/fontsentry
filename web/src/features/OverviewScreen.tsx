import { Card } from "../components/Card";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";
import { Tabs } from "../components/Tabs";
import { DomainsView } from "./DomainsView";
import { Faq } from "./Faq";
import { FindingsTable } from "./FindingsTable";
import { SummaryBar } from "./SummaryBar";
import type { RunMeta, RunReport } from "../lib/api";

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
  if (runs.length === 0) {
    return (
      <Card>
        <p className="text-muted">
          No audits yet. Click <strong>Start audit</strong> (try the demo mode) to produce your
          first report.
        </p>
      </Card>
    );
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

      {report && <SummaryBar report={report} />}

      <Tabs tabs={TABS} active={view} onChange={(id) => onView(id as View)} />

      {loading && <Spinner label="Loading report…" />}

      {report && view === "fonts" && <FindingsTable findings={report.findings} />}
      {report && view === "domains" && <DomainsView domains={report.domains} />}

      <Faq />
    </div>
  );
}
