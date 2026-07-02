import { useEffect, useRef, useState } from "react";
import type { Job } from "../lib/api";

// The scan's real phases, in order (see run_scan in scan.py).
const STEPS = [
  { key: "discover", label: "Discover" },
  { key: "detect", label: "Detect" },
  { key: "score", label: "Score" },
  { key: "report", label: "Report" },
];

function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

export function ScanProgress({ job }: { job: Job }) {
  const activeIndex = Math.max(
    0,
    STEPS.findIndex((s) => s.key === job.phase),
  );
  const determinate = job.total > 0;
  const percent = determinate ? Math.round((job.current / job.total) * 100) : null;

  // Wall-clock elapsed, ticking once a second independent of poll cadence.
  const startedAt = useRef(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // ETA from the observed throughput of the Detect phase (the bulk of the work).
  // Anchored on the first Detect sample so the rate reflects real page timing.
  const detectAnchor = useRef<{ t: number; done: number } | null>(null);
  useEffect(() => {
    if (job.phase === "detect" && detectAnchor.current === null) {
      detectAnchor.current = { t: Date.now(), done: job.current };
    }
  }, [job.phase, job.current]);

  let eta: string;
  if (job.phase === "score" || job.phase === "report") {
    eta = "finishing…";
  } else if (job.phase === "detect" && detectAnchor.current) {
    const { t, done } = detectAnchor.current;
    const dt = now - t;
    const progressed = job.current - done;
    eta =
      progressed > 0 && dt > 0
        ? `~${fmtDuration(((job.total - job.current) / progressed) * dt)}`
        : "estimating…";
  } else {
    // Discover phase: page count is not known yet, so no honest page-based ETA.
    eta = "estimating…";
  }

  return (
    <div
      className="border-b border-stroke bg-surface"
      role="status"
      aria-live="polite"
      aria-label="Audit progress"
    >
      <div className="mx-auto max-w-5xl space-y-2 px-6 py-3">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {STEPS.map((step, i) => {
            const done = i < activeIndex;
            const active = i === activeIndex;
            return (
              <li key={step.key} className="flex items-center gap-2">
                <span
                  className={
                    "flex h-5 w-5 items-center justify-center rounded-full text-xs " +
                    (done
                      ? "bg-accent text-accent-fg"
                      : active
                        ? "border-2 border-accent text-accent"
                        : "border border-stroke text-muted")
                  }
                >
                  {done ? "✓" : i + 1}
                </span>
                <span className={active ? "font-semibold text-ink" : "text-muted"}>
                  {step.label}
                </span>
                {i < STEPS.length - 1 && <span className="text-muted">→</span>}
              </li>
            );
          })}
        </ol>

        <div className="flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-sunken">
            <div
              className={"h-full bg-accent transition-all" + (determinate ? "" : " animate-pulse")}
              style={{ width: determinate ? `${percent}%` : "100%" }}
            />
          </div>
          {determinate && (
            <span className="w-10 text-right font-mono text-sm text-muted">{percent}%</span>
          )}
        </div>

        <div className="flex flex-wrap justify-between gap-x-4 text-sm text-muted">
          <span>
            {job.message || "Starting…"}
            {determinate && <span className="font-mono"> ({job.current}/{job.total})</span>}
          </span>
          <span className="font-mono tabular-nums">
            Elapsed {fmtDuration(now - startedAt.current)} · ETA {eta}
          </span>
        </div>
      </div>
    </div>
  );
}
