import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { api } from "../lib/api";
import type { RunMeta, ScheduleInfo } from "../lib/api";
import type { ToastKind } from "../components/Toast";
import { RunHistory } from "./RunHistory";
import { ScheduleDialog } from "./ScheduleDialog";

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
      <RunHistory runs={runs} selectedId={selectedId} onOpenRun={onOpenRun} />

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
