import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { ScheduleInfo, ScheduleSpec } from "../lib/api";

const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;
type Day = (typeof DAYS)[number];

interface Props {
  onClose: () => void;
  notify: (message: string, kind: ToastKind) => void;
}

export function ScheduleDialog({ onClose, notify }: Props) {
  const [list, setList] = useState<ScheduleInfo[]>([]);
  const [name, setName] = useState("weekly-audit");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("weekly");
  const [time, setTime] = useState("06:00");
  const [day, setDay] = useState<Day>("MON");
  const [mode, setMode] = useState<"demo" | "real">("real");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setList(await api.getSchedules());
    } catch {
      // listing is best-effort
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const spec: ScheduleSpec = { name, frequency, time, day_of_week: day, mode };
    try {
      await api.createSchedule(spec);
      notify("Schedule created", "success");
      await refresh();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Failed to create schedule", "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(target: string) {
    try {
      await api.deleteSchedule(target);
      notify("Schedule removed", "success");
      await refresh();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Failed to remove schedule", "error");
    }
  }

  return (
    <Modal title="Schedule recurring audit" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name">
          <TextInput
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            pattern="[A-Za-z0-9 _\-]+"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Frequency">
            <Select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as "daily" | "weekly")}
            >
              <option value="weekly">weekly</option>
              <option value="daily">daily</option>
            </Select>
          </Field>
          <Field label="Time">
            <TextInput type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          </Field>
        </div>
        {frequency === "weekly" && (
          <Field label="Day">
            <Select value={day} onChange={(e) => setDay(e.target.value as Day)}>
              {DAYS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Mode">
          <Select value={mode} onChange={(e) => setMode(e.target.value as "demo" | "real")}>
            <option value="real">real</option>
            <option value="demo">demo</option>
          </Select>
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button type="submit" disabled={busy}>
            Create
          </Button>
        </div>
      </form>

      {list.length > 0 && (
        <div className="mt-4 border-t border-stroke pt-3">
          <h3 className="mb-2 text-sm font-semibold">Existing schedules</h3>
          <ul className="space-y-1 text-sm">
            {list.map((s) => (
              <li key={s.name} className="flex items-center justify-between gap-2">
                <span>
                  {s.name} {s.next_run && <span className="text-muted">· {s.next_run}</span>}
                </span>
                <Button variant="ghost" onClick={() => remove(s.name)} aria-label={`Delete ${s.name}`}>
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  );
}
