import { cn } from "../lib/cn";
import type { LiveStatus } from "../lib/targets";

const STATUS_TONE: Record<LiveStatus, string> = {
  live: "text-band-low",
  unreachable: "text-band-high",
  unscanned: "text-faint",
};
const STATUS_LABEL: Record<LiveStatus, string> = {
  live: "live",
  unreachable: "unreachable",
  unscanned: "not scanned",
};

const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

// Each listed domain's reachability in the latest run.
export function TargetStatusTable({ rows }: { rows: { domain: string; status: LiveStatus }[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-stroke">
      <table className="w-full border-collapse bg-surface text-sm">
        <caption className="sr-only">Target reachability in the latest run</caption>
        <thead>
          <tr className="bg-surface2 text-left text-muted">
            <th scope="col" className={TH}>
              Domain
            </th>
            <th scope="col" className={TH}>
              Latest run
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.domain} className="border-t border-stroke">
              <td className="px-4 py-2 font-mono text-xs">{r.domain}</td>
              <td className={cn("px-4 py-2 font-medium", STATUS_TONE[r.status])}>
                {STATUS_LABEL[r.status]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
