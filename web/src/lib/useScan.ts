import { useCallback, useEffect, useRef, useState } from "react";
import type { ToastKind } from "../components/Toast";
import { api } from "./api";
import type { Job } from "./api";
import { pollJob } from "./pollJob";

type Mode = "real" | "demo";

// Audit lifecycle for the whole app: start a scan, follow its progress, and on
// load re-attach to one already running on the server (another tab or a prior
// session) so its progress shows here too.
export function useScan(
  notify: (message: string, kind: ToastKind) => void,
  onComplete: (runId: string, mode: Mode) => void,
): {
  scanJob: Job | null;
  scanning: boolean;
  runAudit: (mode: Mode, discoverSubdomains?: boolean, maxPages?: number) => Promise<void>;
} {
  const [scanJob, setScanJob] = useState<Job | null>(null);
  const [scanning, setScanning] = useState(false);

  // Follow a started job to the end; every path ends with scanning cleared.
  const follow = useCallback(
    async (jobId: string, mode: Mode) => {
      try {
        const runId = await pollJob(jobId, setScanJob);
        notify("Audit complete", "success");
        onComplete(runId, mode);
      } catch (e) {
        notify(e instanceof Error ? e.message : "Audit failed", "error");
      } finally {
        setScanning(false);
        setScanJob(null);
      }
    },
    [notify, onComplete],
  );

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
        void follow(job.id, job.mode);
      })
      .catch(() => {
        // no active-jobs endpoint / network hiccup — nothing to adopt
      });
    return () => {
      cancelled = true;
    };
  }, [notify, follow]);

  const runAudit = useCallback(
    async (mode: Mode, discoverSubdomains = false, maxPages?: number) => {
      setScanning(true);
      notify(`Audit started on ${mode === "real" ? "your data" : "demo data"}…`, "info");
      let jobId: string;
      try {
        ({ job_id: jobId } = await api.startScan(mode, discoverSubdomains, maxPages));
      } catch (e) {
        notify(e instanceof Error ? e.message : "Audit failed", "error");
        setScanning(false);
        return;
      }
      await follow(jobId, mode);
    },
    [notify, follow],
  );

  return { scanJob, scanning, runAudit };
}
