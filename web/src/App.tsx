import { useCallback, useState } from "react";
import { AppHeader } from "./components/AppHeader";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import { AuditsScreen } from "./features/AuditsScreen";
import { BackupScreen } from "./features/BackupScreen";
import { HowItWorks } from "./features/HowItWorks";
import { OverviewScreen } from "./features/OverviewScreen";
import type { View } from "./features/OverviewScreen";
import { RegistrySetup } from "./features/RegistrySetup";
import { RulesScreen } from "./features/RulesScreen";
import { RunAuditModal } from "./features/RunAuditModal";
import { ScanControls } from "./features/ScanControls";
import { ScanProgress } from "./features/ScanProgress";
import { TargetsSetup } from "./features/TargetsSetup";
import { useHashRoute } from "./lib/useHashRoute";
import type { Route } from "./lib/useHashRoute";
import { useRunData } from "./lib/useRunData";
import { useScan } from "./lib/useScan";
import { useToast } from "./lib/useToast";

const TITLES: Record<Route, string> = {
  overview: "Overview",
  audits: "Audits",
  registry: "Registry",
  targets: "Targets",
  rules: "Rules",
  backup: "Backup",
  "how-it-works": "How it works",
};

export default function App() {
  const { route, navigate } = useHashRoute();
  const { toast, notify, dismiss } = useToast();
  const data = useRunData(notify);
  const { setSource, setSelectedId, reload } = data;
  const [view, setView] = useState<View>("fonts");
  const [navOpen, setNavOpen] = useState(false); // mobile drawer
  const [auditModalOpen, setAuditModalOpen] = useState(false);

  // Show a run's findings on the Overview (optionally switching data set).
  const openRun = useCallback(
    (runId: string, source?: "real" | "demo") => {
      if (source) setSource(source);
      setSelectedId(runId);
      setView("fonts");
      navigate("overview");
    },
    [navigate, setSource, setSelectedId],
  );

  const onScanComplete = useCallback(
    (runId: string, mode: "real" | "demo") => {
      openRun(runId, mode);
      reload();
    },
    [openRun, reload],
  );
  const { scanJob, scanning, runAudit } = useScan(notify, onScanComplete);

  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[60] focus:rounded-tk focus:bg-surface focus:px-3 focus:py-2 focus:shadow-tk"
      >
        Skip to content
      </a>
      <Sidebar
        route={route}
        onNavigate={navigate}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />

      <div className="min-w-0">
        <AppHeader
          title={TITLES[route]}
          navOpen={navOpen}
          onOpenNav={() => setNavOpen(true)}
          actions={<ScanControls onOpen={() => setAuditModalOpen(true)} running={scanning} />}
        />

        {scanJob && scanJob.status === "running" && <ScanProgress job={scanJob} />}

        <main id="main" tabIndex={-1} className="mx-auto max-w-5xl px-6 py-6">
          {route === "overview" && (
            <OverviewScreen
              runs={data.runs}
              selectedId={data.selectedId}
              onSelect={setSelectedId}
              report={data.report}
              loading={data.loading}
              view={view}
              onView={setView}
              source={data.source}
              onSource={setSource}
            />
          )}
          {route === "audits" && (
            <AuditsScreen
              runs={data.runs}
              selectedId={data.selectedId}
              onOpenRun={openRun}
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
          {route === "backup" && <BackupScreen notify={notify} />}
          {route === "how-it-works" && <HowItWorks />}
        </main>
      </div>

      {auditModalOpen && (
        <RunAuditModal
          onClose={() => setAuditModalOpen(false)}
          onStart={runAudit}
          running={scanning}
        />
      )}
      {toast && <Toast {...toast} onDismiss={dismiss} />}
    </div>
  );
}
