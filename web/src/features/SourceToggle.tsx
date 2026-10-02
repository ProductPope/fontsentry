import { cn } from "../lib/cn";

const SOURCES: { id: "real" | "demo"; label: string }[] = [
  { id: "real", label: "Your data" },
  { id: "demo", label: "Demo data" },
];

interface SourceToggleProps {
  source: "real" | "demo";
  onSource: (source: "real" | "demo") => void;
}

// Switch between the user's own audits and the isolated demo data set.
export function SourceToggle({ source, onSource }: SourceToggleProps) {
  return (
    <div
      role="group"
      aria-label="Data source"
      className="flex rounded-tk border border-stroke bg-surface2 p-0.5"
    >
      {SOURCES.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSource(s.id)}
          aria-pressed={source === s.id}
          className={cn(
            "rounded-chip px-3 py-1 text-sm font-medium transition-colors",
            source === s.id ? "bg-surface text-ink shadow-tk" : "text-muted hover:text-ink",
          )}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
