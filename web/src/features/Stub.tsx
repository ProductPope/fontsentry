import { Card } from "../components/Card";

// Placeholder for comp sections not yet wired to the backend (Audits, Rules).
export function Stub({ title }: { title: string }) {
  return (
    <Card className="text-center">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted">This section is being designed next.</p>
    </Card>
  );
}
