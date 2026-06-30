import { useCallback, useEffect, useState } from "react";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { Select } from "./components/Select";
import { Spinner } from "./components/Spinner";
import { Toast } from "./components/Toast";
import type { ToastKind, ToastState } from "./components/Toast";
import { DiffView } from "./features/DiffView";
import { FindingsTable } from "./features/FindingsTable";
import { ScanControls } from "./features/ScanControls";
import { ScheduleDialog } from "./features/ScheduleDialog";
import { SummaryCards } from "./features/SummaryCards";
import { api } from "./lib/api";
import type { RunMeta, RunReport } from "./lib/api";

type View = "findings" | "diff";

export default function App() {
  const [runs, setRuns] = useState<RunMeta[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("findings");
  const [scheduleOpen, setScheduleOpen] = useState(false);
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
      setView("findings");
    },
    [refreshRuns],
  );

  return (
    <div className="min-h-screen">
      <header className="border-b border-stroke bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div>
            <h1 className="text-lg font-bold">FontSentry</h1>
            <p className="text-sm text-muted">heuristic estimate · not legal advice</p>
          </div>
          <div className="flex items-center gap-2">
            <ScanControls onComplete={onScanComplete} notify={notify} />
            <Button variant="secondary" onClick={() => setScheduleOpen(true)}>
              Schedule
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-6 py-6">
        {runs.length === 0 ? (
          <Card>
            <p className="text-muted">
              No audits yet. Click <strong>Start audit</strong> (try the demo mode) to produce
              your first report.
            </p>
          </Card>
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <label className="text-sm">
                <span className="mb-1 block font-medium">Run</span>
                <Select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.id}
                    </option>
                  ))}
                </Select>
              </label>
              <div role="tablist" aria-label="View" className="flex gap-1">
                <Button
                  role="tab"
                  aria-selected={view === "findings"}
                  variant={view === "findings" ? "primary" : "ghost"}
                  onClick={() => setView("findings")}
                >
                  Findings
                </Button>
                <Button
                  role="tab"
                  aria-selected={view === "diff"}
                  variant={view === "diff" ? "primary" : "ghost"}
                  onClick={() => setView("diff")}
                >
                  Diff
                </Button>
              </div>
            </div>

            {loading && <Spinner label="Loading report…" />}

            {report && view === "findings" && (
              <>
                <SummaryCards summary={report.summary} />
                <FindingsTable findings={report.findings} />
              </>
            )}

            {view === "diff" && <DiffView runs={runs} currentId={selectedId} />}
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
