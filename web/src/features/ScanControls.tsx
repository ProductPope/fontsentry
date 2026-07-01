import { useState } from "react";
import { Button } from "../components/Button";
import { Select } from "../components/Select";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { Job } from "../lib/api";

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

interface ScanControlsProps {
  onComplete: (runId: string) => void;
  notify: (message: string, kind: ToastKind) => void;
  onProgress: (job: Job | null) => void;
}

export function ScanControls({ onComplete, notify, onProgress }: ScanControlsProps) {
  const [mode, setMode] = useState<"demo" | "real">("demo");
  const [running, setRunning] = useState(false);

  async function start() {
    setRunning(true);
    notify("Audit started…", "info");
    try {
      const { job_id } = await api.startScan(mode);
      const runId = await pollJob(job_id, onProgress);
      notify("Audit complete", "success");
      onComplete(runId);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Audit failed", "error");
    } finally {
      setRunning(false);
      onProgress(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Select
        aria-label="Scan mode"
        value={mode}
        onChange={(e) => setMode(e.target.value as "demo" | "real")}
        className="w-auto"
        disabled={running}
      >
        <option value="demo">demo</option>
        <option value="real">real</option>
      </Select>
      <Button onClick={start} disabled={running}>
        {running ? "Auditing…" : "Start audit"}
      </Button>
    </div>
  );
}
