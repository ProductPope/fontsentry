import { useCallback, useEffect, useState } from "react";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { Select } from "./components/Select";
import { Spinner } from "./components/Spinner";
import { Tabs } from "./components/Tabs";
import { ThemeToggle } from "./components/ThemeToggle";
import { Toast } from "./components/Toast";
import type { ToastKind, ToastState } from "./components/Toast";
import { DomainsView } from "./features/DomainsView";
import { Faq } from "./features/Faq";
import { FindingsTable } from "./features/FindingsTable";
import { ScanControls } from "./features/ScanControls";
import { ScanProgress } from "./features/ScanProgress";
import { ScheduleDialog } from "./features/ScheduleDialog";
import { SetupSection } from "./features/SetupSection";
import { SummaryBar } from "./features/SummaryBar";
import { api } from "./lib/api";
import type { Job, RunMeta, RunReport } from "./lib/api";

type View = "fonts" | "domains";

const TABS = [
  { id: "fonts", label: "Fonts" },
  { id: "domains", label: "Domains" },
];

export default function App() {
  const [runs, setRuns] = useState<RunMeta[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("fonts");
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scanJob, setScanJob] = useState<Job | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  const notify = useCallback((message: string, kind: ToastKind) => {
    setToast({ message, kind });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const refreshRuns = useCallback(async () => {
    const list = await api.getRuns();
    setRuns(list);
    setSelectedId((prev) => prev || list[0]?.id || "");
  }, []);

  useEffect(() => {
    refreshRuns().catch((e: unknown) =>
      notify(e instanceof Error ? e.message : "Could not load runs", "error"),
    );
  }, [refreshRuns, notify]);

  useEffect(() => {
    if (!selectedId) {
      setReport(null);
      return;
    }
    setLoading(true);
    api
      .getRun(selectedId)
      .then(setReport)
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load run", "error"),
      )
      .finally(() => setLoading(false));
  }, [selectedId, notify]);

  const onScanComplete = useCallback(
    async (runId: string) => {
      await refreshRuns();
      setSelectedId(runId);
      setView("fonts");
    },
    [refreshRuns],
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-stroke bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div>
            <h1 className="text-lg font-bold">FontSentry</h1>
            <p className="text-sm text-muted">heuristic estimate · not legal advice</p>
          </div>
          <div className="flex items-center gap-2">
            <ScanControls onComplete={onScanComplete} notify={notify} onProgress={setScanJob} />
            <Button variant="secondary" onClick={() => setScheduleOpen(true)}>
              Schedule
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {scanJob && scanJob.status === "running" && <ScanProgress job={scanJob} />}

      <main className="mx-auto max-w-5xl space-y-5 px-6 py-6">
        <SetupSection notify={notify} />

        {runs.length === 0 ? (
          <Card>
            <p className="text-muted">
              No audits yet. Click <strong>Start audit</strong> (try the demo mode) to produce
              your first report.
            </p>
          </Card>
        ) : (
          <>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Run</span>
              <Select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
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

            <Tabs tabs={TABS} active={view} onChange={(id) => setView(id as View)} />

            {loading && <Spinner label="Loading report…" />}

            {report && view === "fonts" && <FindingsTable findings={report.findings} />}
            {report && view === "domains" && <DomainsView domains={report.domains} />}

            <Faq />
          </>
        )}
      </main>

      {scheduleOpen && (
        <ScheduleDialog onClose={() => setScheduleOpen(false)} notify={notify} />
      )}
      {toast && <Toast {...toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
