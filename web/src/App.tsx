import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { RiskBadge } from "./components/Badge";
import { Spinner } from "./components/Spinner";

// Phase C shell + a small design-system check. Replaced by the real dashboard
// in the next phase; the components and tokens below are the foundation.
export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-stroke bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-bold">FontSentry</h1>
          <p className="text-sm text-muted">heuristic estimate · not legal advice</p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <Card>
          <h2 className="mb-3 text-base font-semibold">Design system check</h2>
          <div className="flex flex-wrap items-center gap-3">
            <Button>Start audit</Button>
            <Button variant="secondary">Schedule</Button>
            <Button variant="ghost">Cancel</Button>
            <RiskBadge band="low" />
            <RiskBadge band="medium" />
            <RiskBadge band="high" />
            <Spinner label="Scanning…" />
          </div>
        </Card>
      </main>
    </div>
  );
}
