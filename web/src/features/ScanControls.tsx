import { useState } from "react";
import { Button } from "../components/Button";
import { cn } from "../lib/cn";

export type ScanMode = "real" | "demo";

// "Your data" is the default: once a user has added their domains, an audit
// should run against them, not the sample dataset. Demo is an explicit opt-in.
const MODES: { id: ScanMode; label: string }[] = [
  { id: "real", label: "Your data" },
  { id: "demo", label: "Demo data" },
];

interface ScanControlsProps {
  onStart: (mode: ScanMode) => void;
  running: boolean;
}

export function ScanControls({ onStart, running }: ScanControlsProps) {
  const [mode, setMode] = useState<ScanMode>("real");

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
      <Button onClick={() => onStart(mode)} disabled={running}>
        {running ? "Auditing…" : "Start audit"}
      </Button>
    </div>
  );
}
