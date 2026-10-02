import { Button } from "../components/Button";
import { Card } from "../components/Card";

interface TargetsSavedProps {
  count: number;
  running: boolean;
  onRunAudit: () => void;
  onEdit: () => void;
}

// Success step after a save that changed the domain list: run an audit now, or
// go back to editing.
export function TargetsSaved({ count, running, onRunAudit, onEdit }: TargetsSavedProps) {
  return (
    <section className="max-w-xl">
      <Card className="space-y-4 text-center">
        <div>
          <div
            className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-band-low-bg text-band-low"
            aria-hidden="true"
          >
            ✓
          </div>
          <h2 className="mt-2 text-base font-semibold">Domains saved</h2>
          <p className="mt-1 text-sm text-muted">
            {count} domain{count === 1 ? "" : "s"} saved to your local config. Run an audit to scan
            them now, or keep editing the list.
          </p>
        </div>
        <div className="flex justify-center gap-2">
          <Button onClick={onRunAudit} disabled={running}>
            {running ? "Auditing…" : "Run audit"}
          </Button>
          <Button variant="secondary" onClick={onEdit} disabled={running}>
            Edit domains
          </Button>
        </div>
      </Card>
    </section>
  );
}
