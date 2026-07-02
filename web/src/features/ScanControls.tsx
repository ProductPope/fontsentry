import { useState } from "react";
import { Button } from "../components/Button";
import type { ToastKind } from "../components/Toast";
import { cn } from "../lib/cn";
import { api } from "../lib/api";
import type { Job } from "../lib/api";

type Mode = "real" | "demo";

// "Your data" is the default: once a user has added their own domains, an audit
// should run against them, not the sample dataset. Demo is an explicit opt-in.
const MODES: { id: Mode; label: string }[] = [
  { id: "real", label: "Your data" },
  { id: "demo", label: "Demo data" },
];

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
  const [mode, setMode] = useState<Mode>("real");
  const [running, setRunning] = useState(false);

  async function start() {
    setRunning(true);
    notify(`Audit started on ${mode === "real" ? "your data" : "demo data"}…`, "info");
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
      <div
        role="group"
        aria-label="Data source"
        className="flex rounded-tk border border-stroke bg-surface2 p-0.5"
      >
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            disabled={running}
            aria-pressed={mode === m.id}
            className={cn(
              "rounded-chip px-3 py-1 text-sm font-medium transition-colors",
              mode === m.id ? "bg-surface text-ink shadow-tk" : "text-muted hover:text-ink",
            )}
          >
            {m.label}
          </button>
        ))}
      </div>
      <Button onClick={start} disabled={running}>
        {running ? "Auditing…" : "Start audit"}
      </Button>
    </div>
  );
}
