import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import type { ToastKind, ToastState } from "./components/Toast";
import { AuditsScreen } from "./features/AuditsScreen";
import { OverviewScreen } from "./features/OverviewScreen";
import type { View } from "./features/OverviewScreen";
import { RegistrySetup } from "./features/RegistrySetup";
import { RulesScreen } from "./features/RulesScreen";
import { RunAuditModal } from "./features/RunAuditModal";
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

async function pollJob(jobId: string, onProgress: (job: Job) => void): Promise<string> {
  for (let i = 0; i < 600; i++) {
    const job = await api.getJob(jobId);
    onProgress(job);
    if (job.status === "done" && job.run_id) return job.run_id;
    if (job.status === "error") throw new Error(job.error ?? "scan failed");
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("scan timed out");
}

export default function App() {
  const { route, navigate } = useHashRoute();

  const [runs, setRuns] = useState<RunMeta[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("fonts");
  // Which data set the Overview shows: real ("Your data") vs isolated demo runs.
  const [viewSource, setViewSource] = useState<"real" | "demo">("real");
  const [refreshKey, setRefreshKey] = useState(0);
  const [scanJob, setScanJob] = useState<Job | null>(null);
  const [scanning, setScanning] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [navOpen, setNavOpen] = useState(false); // mobile drawer
  const [auditModalOpen, setAuditModalOpen] = useState(false);

  const notify = useCallback((message: string, kind: ToastKind) => {
    setToast({ message, kind });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // Load the run list for the active source. Keep the current selection if it
  // still exists, otherwise fall back to the newest run. refreshKey lets a
  // just-finished scan force a reload even when the source didn't change.
  useEffect(() => {
    let cancelled = false;
    api
      .getRuns(viewSource)
      .then((list) => {
        if (cancelled) return;
        setRuns(list);
        setSelectedId((prev) => (list.some((r) => r.id === prev) ? prev : list[0]?.id || ""));
      })
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load runs", "error"),
      );
    return () => {
      cancelled = true;
    };
  }, [viewSource, refreshKey, notify]);

  useEffect(() => {
    if (!selectedId) {
      setReport(null);
      return;
    }
    setLoading(true);
    api
      .getRun(selectedId, viewSource)
      .then(setReport)
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load run", "error"),
      )
      .finally(() => setLoading(false));
  }, [selectedId, viewSource, notify]);

  const onScanComplete = useCallback(
    (runId: string, mode: "real" | "demo") => {
      setViewSource(mode);
      setSelectedId(runId);
      setRefreshKey((k) => k + 1);
      setView("fonts");
      navigate("overview");
    },
    [navigate],
  );

  const onOpenRun = useCallback(
    (runId: string) => {
      setSelectedId(runId);
      setView("fonts");
      navigate("overview");
    },
    [navigate],
  );

  // On load, re-attach to a scan already running on the server (started from the
  // CLI, another tab, or a prior session) so its progress shows here too.
  const adopted = useRef(false);
  useEffect(() => {
    if (adopted.current) return;
    let cancelled = false;
    api
      .getActiveJobs()
      .then((active) => {
        const job = active[0];
        if (cancelled || adopted.current || !job) return;
        adopted.current = true;
        setScanning(true);
        setScanJob(job);
        notify("Reattached to a running audit…", "info");
        pollJob(job.id, setScanJob)
          .then((runId) => {
            notify("Audit complete", "success");
            onScanComplete(runId, job.mode);
          })
          .catch((e: unknown) => notify(e instanceof Error ? e.message : "Audit failed", "error"))
          .finally(() => {
            setScanning(false);
            setScanJob(null);
          });
      })
      .catch(() => {
        // no active-jobs endpoint / network hiccup — nothing to adopt
      });
    return () => {
      cancelled = true;
    };
  }, [notify, onScanComplete]);

  const runAudit = useCallback(
    async (mode: "real" | "demo", discoverSubdomains = false, maxPages?: number) => {
      setScanning(true);
      notify(`Audit started on ${mode === "real" ? "your data" : "demo data"}…`, "info");
      try {
        const { job_id } = await api.startScan(mode, discoverSubdomains, maxPages);
        const runId = await pollJob(job_id, setScanJob);
        notify("Audit complete", "success");
        onScanComplete(runId, mode);
      } catch (e) {
        notify(e instanceof Error ? e.message : "Audit failed", "error");
      } finally {
        setScanning(false);
        setScanJob(null);
      }
    },
    [notify, onScanComplete],
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
              <ScanControls onOpen={() => setAuditModalOpen(true)} running={scanning} />
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
              source={viewSource}
              onSource={setViewSource}
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
          {route === "targets" && (
            <TargetsSetup
              notify={notify}
              onRunAudit={() => setAuditModalOpen(true)}
              running={scanning}
            />
          )}
          {route === "rules" && <RulesScreen notify={notify} />}
        </main>
      </div>

      {auditModalOpen && (
        <RunAuditModal
          onClose={() => setAuditModalOpen(false)}
          onStart={runAudit}
          running={scanning}
        />
      )}
      {toast && <Toast {...toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
