import { useCallback, useEffect, useState } from "react";
import { Button } from "./components/Button";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import type { ToastKind, ToastState } from "./components/Toast";
import { OverviewScreen } from "./features/OverviewScreen";
import type { View } from "./features/OverviewScreen";
import { RegistrySetup } from "./features/RegistrySetup";
import { ScanControls } from "./features/ScanControls";
import { ScanProgress } from "./features/ScanProgress";
import { ScheduleDialog } from "./features/ScheduleDialog";
import { Stub } from "./features/Stub";
import { TargetsSetup } from "./features/TargetsSetup";
import { api } from "./lib/api";
import type { Job, RunMeta, RunReport } from "./lib/api";
import { useHashRoute } from "./lib/useHashRoute";
import type { Route } from "./lib/useHashRoute";

const TITLES: Record<Route, string> = {
  overview: "Overview",
  audits: "Audits",
  registry: "Registry",
  targets: "Targets",
  rules: "Rules",
};

export default function App() {
  const { route, navigate } = useHashRoute();

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
      navigate("overview");
    },
    [refreshRuns, navigate],
  );

  return (
    <div className="grid min-h-screen grid-cols-[248px_minmax(0,1fr)]">
      <Sidebar route={route} onNavigate={navigate} />

      <div className="min-w-0">
        <header className="sticky top-0 z-40 border-b border-stroke bg-surface/85 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
            <h1 className="text-lg font-bold">{TITLES[route]}</h1>
            <div className="flex items-center gap-2">
              <ScanControls onComplete={onScanComplete} notify={notify} onProgress={setScanJob} />
              <Button variant="secondary" onClick={() => setScheduleOpen(true)}>
                Schedule
              </Button>
            </div>
          </div>
        </header>

        {scanJob && scanJob.status === "running" && <ScanProgress job={scanJob} />}

        <main className="mx-auto max-w-5xl px-6 py-6">
          {route === "overview" && (
            <OverviewScreen
              runs={runs}
              selectedId={selectedId}
              onSelect={setSelectedId}
              report={report}
              loading={loading}
              view={view}
              onView={setView}
            />
          )}
          {route === "audits" && <Stub title="Audits" />}
          {route === "registry" && <RegistrySetup notify={notify} />}
          {route === "targets" && <TargetsSetup notify={notify} />}
          {route === "rules" && <Stub title="Rules" />}
        </main>
      </div>

      {scheduleOpen && <ScheduleDialog onClose={() => setScheduleOpen(false)} notify={notify} />}
      {toast && <Toast {...toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
