import { Card } from "../components/Card";
import { Sparkline } from "../components/Sparkline";
import type { LicenseVerdict } from "../lib/api";
import { cn } from "../lib/cn";
import { deltaText, openCount } from "../lib/overview";
import type { OverviewStats, VerdictCounts } from "../lib/overview";

const VERDICT_TONE: Record<LicenseVerdict, string> = {
  violation: "text-band-high",
  needs_check: "text-band-medium",
  ok: "text-band-low",
};

interface RiskPostureProps {
  stats: OverviewStats;
  prev: VerdictCounts | null; // the previous run's counts, for deltas
  trend: number[]; // findings needing action per run, oldest → newest
}

// Headline numbers for the selected run: privacy warning, license-risk bands
// with "vs last run" deltas, portfolio size, and the active-findings trend.
export function RiskPosture({ stats, prev, trend }: RiskPostureProps) {
  const { byVerdict } = stats;
  const delta = (v: LicenseVerdict) => (prev ? byVerdict[v] - prev[v] : undefined);
  const currentOpen = openCount(byVerdict);

  return (
    <>
      {stats.privacyFlagged > 0 && (
        <div className="rounded-card border-l-4 border-band-medium bg-band-medium-bg/40 px-4 py-3 text-sm">
          <span className="font-semibold text-band-medium">⚠ Privacy (GDPR/RODO): </span>
          {stats.privacyFlagged} font{stats.privacyFlagged === 1 ? "" : "s"} load from third
          parties (e.g. the Google Fonts API), sending visitor IPs off-site. Self-host them to stay
          compliant — open the <strong>Privacy (GDPR)</strong> filter under Fonts for the list and
          the fix.
        </div>
      )}

      <div className="text-xs font-semibold uppercase tracking-wide text-faint">License risk</div>
      <h2 className="sr-only">Risk posture</h2>
      <section aria-label="Risk posture" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Posture
          label="Violation"
          count={byVerdict.violation}
          tone={VERDICT_TONE.violation}
          delta={delta("violation")}
        />
        <Posture
          label="Need check"
          count={byVerdict.needs_check}
          tone={VERDICT_TONE.needs_check}
          delta={delta("needs_check")}
        />
        <Posture label="OK" count={byVerdict.ok} tone={VERDICT_TONE.ok} delta={delta("ok")} />
        <Posture label="Privacy" count={stats.privacyFlagged} tone="text-band-medium" />
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <div className="mb-2 text-xs uppercase tracking-wide text-faint">Portfolio</div>
          <div className="grid grid-cols-2 gap-3">
            <Sub label="Domains" value={stats.domains} />
            <Sub label="Live" value={stats.live} />
            <Sub label="Unreachable" value={stats.unreachable} />
            <Sub label="Clean" value={stats.clean} />
          </div>
        </Card>

        {trend.length >= 2 && (
          <Card>
            <div className="text-xs uppercase tracking-wide text-faint">Active findings over time</div>
            <div className="mt-2 flex items-end justify-between gap-4">
              <div>
                <span className="font-mono text-2xl font-bold tabular-nums">{currentOpen}</span>
                {prev && (
                  <span className="ml-2 text-xs text-faint">
                    {deltaText(currentOpen - openCount(prev))} vs last run
                  </span>
                )}
              </div>
              <Sparkline values={trend} label={`Active findings across the last ${trend.length} audits`} />
            </div>
          </Card>
        )}
      </div>
    </>
  );
}

// Active (open) finding count for a risk band, with an optional "vs last run" delta.
function Posture({
  label,
  count,
  tone,
  delta,
}: {
  label: string;
  count: number;
  tone: string;
  delta?: number;
}) {
  return (
    <Card>
      <div className={cn("font-mono text-2xl font-bold tabular-nums", tone)}>{count}</div>
      <div className="text-xs uppercase tracking-wide text-faint">{label}</div>
      {delta !== undefined && (
        <div className="mt-0.5 font-mono text-xs text-faint">{deltaText(delta)} vs last</div>
      )}
    </Card>
  );
}

function Sub({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-mono text-xl font-bold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}
