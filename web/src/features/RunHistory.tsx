import { Card } from "../components/Card";
import type { LicenseVerdict, RunMeta } from "../lib/api";
import { cn } from "../lib/cn";

const VERDICT_ORDER: LicenseVerdict[] = ["violation", "needs_check", "ok"];
const VERDICT_TEXT: Record<LicenseVerdict, string> = {
  violation: "text-band-high",
  needs_check: "text-band-medium",
  ok: "text-band-low",
};
const VERDICT_LABEL: Record<LicenseVerdict, string> = {
  violation: "violation",
  needs_check: "need check",
  ok: "ok",
};

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

interface RunHistoryProps {
  runs: RunMeta[];
  selectedId: string;
  onOpenRun: (id: string) => void;
}

// Past audits, newest first, each with its verdict counts; click to open one.
export function RunHistory({ runs, selectedId, onOpenRun }: RunHistoryProps) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Audit history</h2>
      {runs.length === 0 ? (
        <Card>
          <p className="text-muted">No audits yet. Start one from the header.</p>
        </Card>
      ) : (
        <ol className="space-y-2">
          {runs.map((r) => {
            const active = r.id === selectedId;
            return (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => onOpenRun(r.id)}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "w-full rounded-card border bg-surface p-3 text-left shadow-tk transition-colors",
                    active ? "border-accent" : "border-stroke hover:bg-surface2",
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs text-muted">{r.id}</span>
                    <span className="text-xs text-faint">{fmtDate(r.generated_at)}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-sm">
                    {VERDICT_ORDER.map((v) => (
                      <span key={v} className={cn("font-mono tabular-nums", VERDICT_TEXT[v])}>
                        {r.summary.by_verdict[v] ?? 0} {VERDICT_LABEL[v]}
                      </span>
                    ))}
                    <span className="font-mono tabular-nums text-muted">
                      {r.summary.needs_action}/{r.summary.total_findings} need action
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
