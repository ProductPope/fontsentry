import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { cn } from "../lib/cn";
import { api } from "../lib/api";
import type { LicenseVerdict, RunMeta, ScheduleInfo } from "../lib/api";
import type { ToastKind } from "../components/Toast";
import { ScheduleDialog } from "./ScheduleDialog";

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

interface AuditsScreenProps {
  runs: RunMeta[];
  selectedId: string;
  onOpenRun: (id: string) => void;
  notify: (message: string, kind: ToastKind) => void;
}

export function AuditsScreen({ runs, selectedId, onOpenRun, notify }: AuditsScreenProps) {
  const [schedules, setSchedules] = useState<ScheduleInfo[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const refreshSchedules = useCallback(() => {
    api
      .getSchedules()
      .then(setSchedules)
      .catch(() => {
        // listing is best-effort (empty on platforms without a scheduler backend)
      });
  }, []);

  useEffect(() => {
    refreshSchedules();
  }, [refreshSchedules]);

  async function removeSchedule(name: string) {
    try {
      await api.deleteSchedule(name);
      notify("Schedule removed", "success");
      refreshSchedules();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Failed to remove schedule", "error");
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
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

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Schedules</h2>
          <Button variant="secondary" onClick={() => setDialogOpen(true)}>
            New schedule
          </Button>
        </div>
        {schedules.length === 0 ? (
          <Card>
            <p className="text-sm text-muted">No recurring audits scheduled.</p>
          </Card>
        ) : (
          <ul className="space-y-2">
            {schedules.map((s) => (
              <li key={s.name}>
                <Card className="flex items-start justify-between gap-2 p-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{s.name}</div>
                    {s.next_run && (
                      <div className="font-mono text-xs text-muted">next {s.next_run}</div>
                    )}
                    {s.status && <div className="text-xs text-faint">{s.status}</div>}
                  </div>
                  <Button
                    variant="ghost"
                    className="px-2"
                    aria-label={`Delete ${s.name}`}
                    onClick={() => removeSchedule(s.name)}
                  >
                    ✕
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      {dialogOpen && (
        <ScheduleDialog
          notify={notify}
          onClose={() => {
            setDialogOpen(false);
            refreshSchedules();
          }}
        />
      )}
    </div>
  );
}
