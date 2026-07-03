import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Modal } from "../components/Modal";
import { TextInput } from "../components/TextInput";
import { cn } from "../lib/cn";
import { api } from "../lib/api";
import type { ScanEstimate } from "../lib/api";
import type { ScanMode } from "./ScanControls";

const MODES: { id: ScanMode; label: string }[] = [
  { id: "real", label: "Your data" },
  { id: "demo", label: "Demo data" },
];

const DEMO_HOSTS = 2; // the offline demo dataset

function fmtEta(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  return m > 0 ? `~${m}m ${s % 60}s` : `~${s}s`;
}

interface RunAuditModalProps {
  onClose: () => void;
  onStart: (mode: ScanMode, discoverSubdomains: boolean, maxPages: number) => void;
  running: boolean;
}

export function RunAuditModal({ onClose, onStart, running }: RunAuditModalProps) {
  const [mode, setMode] = useState<ScanMode>("real");
  const [discover, setDiscover] = useState(false);
  const [maxPages, setMaxPages] = useState(25);
  const [realHosts, setRealHosts] = useState<number | null>(null);
  const [estimate, setEstimate] = useState<ScanEstimate | null>(null);

  useEffect(() => {
    api
      .getTargets()
      .then((t) => setRealHosts(t.targets.length))
      .catch(() => setRealHosts(null));
  }, []);

  const hosts = mode === "real" ? (realHosts ?? 0) : DEMO_HOSTS;
  const pages = Math.max(1, Math.round(maxPages) || 1);

  useEffect(() => {
    let cancelled = false;
    setEstimate(null);
    api
      .scanEstimate(hosts, pages)
      .then((e) => {
        if (!cancelled) setEstimate(e);
      })
      .catch(() => {
        if (!cancelled) setEstimate(null);
      });
    return () => {
      cancelled = true;
    };
  }, [hosts, pages]);

  return (
    <Modal title="Run audit" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <span className="mb-1 block text-sm font-medium">Data source</span>
          <div className="flex rounded-tk border border-stroke bg-surface2 p-0.5">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                aria-pressed={mode === m.id}
                className={cn(
                  "flex-1 rounded-chip px-3 py-1 text-sm font-medium transition-colors",
                  mode === m.id ? "bg-surface text-ink shadow-tk" : "text-muted hover:text-ink",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Max pages per domain</span>
          <TextInput
            type="number"
            min={1}
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            className="w-32"
          />
        </label>

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={discover}
            disabled={mode !== "real"}
            onChange={(e) => setDiscover(e.target.checked)}
          />
          <span className={mode !== "real" ? "text-faint" : ""}>
            <span className="font-medium">Check subdomains</span> — find public subdomains via
            Certificate Transparency and audit each as its own host.{" "}
            <span className="text-faint">Queries an external service; your data only.</span>
          </span>
        </label>

        <div className="rounded-tk bg-surface2 px-3 py-2 text-sm">
          <span className="text-faint">Estimated time: </span>
          {estimate === null ? (
            <span className="text-muted">estimating…</span>
          ) : estimate.eta_seconds === null ? (
            <span className="text-muted">no estimate yet (first audit)</span>
          ) : (
            <span className="font-medium text-ink">
              {fmtEta(estimate.eta_seconds)}{" "}
              <span className="text-faint">(from {estimate.based_on_runs} past audits)</span>
              {discover && <span className="text-faint"> — excludes discovered subdomains</span>}
            </span>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={running}
            onClick={() => {
              onStart(mode, mode === "real" && discover, pages);
              onClose();
            }}
          >
            {running ? "Auditing…" : "Start audit"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
