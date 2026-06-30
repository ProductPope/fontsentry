import { Card } from "../components/Card";
import type { Band, RunSummary } from "../lib/api";

const BANDS: Band[] = ["high", "medium", "low"];

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <Card>
      <div className="text-2xl font-bold tabular-nums">{n}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
    </Card>
  );
}

export function SummaryCards({ summary }: { summary: RunSummary }) {
  return (
    <section aria-label="Summary" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Stat n={summary.total_findings} label="Findings" />
      <Stat n={summary.open_findings} label="Open" />
      <Stat n={summary.resolved_findings} label="Resolved" />
      {BANDS.map((band) => (
        <Stat key={band} n={summary.by_band[band] ?? 0} label={band} />
      ))}
    </section>
  );
}
