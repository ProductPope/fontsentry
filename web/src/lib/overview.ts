import type { LicenseVerdict, RunReport } from "./api";
import { isPrivacyFlagged } from "./privacy";

export type VerdictCounts = Record<LicenseVerdict, number>;

export function countByVerdict(report: RunReport): VerdictCounts {
  const counts: VerdictCounts = { violation: 0, needs_check: 0, ok: 0 };
  for (const f of report.findings) counts[f.license_verdict] += 1;
  return counts;
}

// "↑3" / "↓2" / "±0" — a change vs the previous run.
export function deltaText(d: number): string {
  if (d > 0) return `↑${d}`;
  if (d < 0) return `↓${-d}`;
  return "±0";
}

export interface OverviewStats {
  byVerdict: VerdictCounts;
  domains: number;
  live: number;
  unreachable: number;
  clean: number; // every font on the domain is OK
  privacyFlagged: number; // findings delivered by a third party
}

export function overviewStats(report: RunReport): OverviewStats {
  const domains = report.domains.length;
  const live = report.domains.filter((d) => d.is_live).length;
  return {
    byVerdict: countByVerdict(report),
    domains,
    live,
    unreachable: domains - live,
    clean: report.domains.filter((d) => d.fonts.every((f) => f.license_verdict === "ok")).length,
    privacyFlagged: report.findings.filter(isPrivacyFlagged).length,
  };
}

// Findings still needing attention (violation + needs check).
export function openCount(counts: VerdictCounts): number {
  return counts.violation + counts.needs_check;
}
