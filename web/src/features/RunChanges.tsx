import { Card } from "../components/Card";
import type { DiffResult } from "../lib/api";
import { cn } from "../lib/cn";

// Per-finding changes of the selected run vs the one before it.
export function RunChanges({ diff }: { diff: DiffResult }) {
  const any = diff.new_findings.length || diff.resolved_findings.length || diff.changed.length;
  return (
    <Card>
      <div className="text-xs uppercase tracking-wide text-faint">Changes since last run</div>
      {any ? (
        <div className="mt-2 space-y-2 text-sm">
          {diff.new_findings.length > 0 && (
            <ChangeRow
              tone="text-band-high"
              label="New"
              items={diff.new_findings.map((f) => f.family)}
            />
          )}
          {diff.resolved_findings.length > 0 && (
            <ChangeRow
              tone="text-band-low"
              label="Resolved"
              items={diff.resolved_findings.map((f) => f.family)}
            />
          )}
          {diff.changed.length > 0 && (
            <ChangeRow
              tone="text-band-medium"
              label="Changed"
              items={diff.changed.map((c) => `${c.family} (${c.old_verdict}→${c.new_verdict})`)}
            />
          )}
        </div>
      ) : (
        <p className="mt-1 text-sm text-muted">No changes since the last run.</p>
      )}
    </Card>
  );
}

function ChangeRow({ tone, label, items }: { tone: string; label: string; items: string[] }) {
  return (
    <div>
      <span className={cn("font-medium", tone)}>
        {label} ({items.length})
      </span>{" "}
      <span className="text-muted">{items.join(", ")}</span>
    </div>
  );
}
