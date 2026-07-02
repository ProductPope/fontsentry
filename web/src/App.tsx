import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import type { ToastKind, ToastState } from "./components/Toast";
import { AuditsScreen } from "./features/AuditsScreen";
import { OverviewScreen } from "./features/OverviewScreen";
import type { View } from "./features/OverviewScreen";
import { RegistrySetup } from "./features/RegistrySetup";
import { RulesScreen } from "./features/RulesScreen";
import { ScanControls } from "./features/ScanControls";
import { ScanProgress } from "./features/ScanProgress";
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
  const [scanJob, setScanJob] = useState<Job | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [navOpen, setNavOpen] = useState(false); // mobile drawer

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

  const onOpenRun = useCallback(
    (runId: string) => {
      setSelectedId(runId);
      setView("fonts");
      navigate("overview");
    },
    [navigate],
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <Sidebar
        route={route}
        onNavigate={navigate}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />

      <div className="min-w-0">
        <header className="sticky top-0 z-40 border-b border-stroke bg-surface/85 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setNavOpen(true)}
                aria-label="Open navigation"
                aria-controls="app-sidebar"
                aria-expanded={navOpen}
                className="-ml-1 rounded-tk p-1 text-muted hover:text-ink md:hidden"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M4 7h16M4 12h16M4 17h16"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
              <h1 className="text-lg font-bold">{TITLES[route]}</h1>
            </div>
            <div className="flex items-center gap-2">
              <ScanControls onComplete={onScanComplete} notify={notify} onProgress={setScanJob} />
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
          {route === "audits" && (
            <AuditsScreen
              runs={runs}
              selectedId={selectedId}
              onOpenRun={onOpenRun}
              notify={notify}
            />
          )}
          {route === "registry" && <RegistrySetup notify={notify} />}
          {route === "targets" && <TargetsSetup notify={notify} />}
          {route === "rules" && <RulesScreen notify={notify} />}
        </main>
      </div>

      {toast && <Toast {...toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
