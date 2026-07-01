import { useMemo } from "react";
import { Card } from "../components/Card";
import type { Finding, RunReport } from "../lib/api";

function isSystemOnly(f: Finding): boolean {
  return f.embeddings.length > 0 && f.embeddings.every((e) => e === "system");
}

function Stat({ value, label, note }: { value: number; label: string; note?: string }) {
  return (
    <Card>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      {note && <div className="mt-0.5 text-xs text-muted">{note}</div>}
    </Card>
  );
}

// One run summary, independent of the active tab.
export function SummaryBar({ report }: { report: RunReport }) {
  const stats = useMemo(() => {
    const domains = report.domains.length;
    const live = report.domains.filter((d) => d.is_live).length;

    const webFonts = report.findings.filter((f) => !isSystemOnly(f));
    const families = webFonts.length;

    const formats = new Set(
      webFonts.flatMap((f) => f.formats).filter((x) => x && x !== "unknown"),
    );

    const warnings = report.findings.filter(
      (f) => f.status === "open" && (f.band === "high" || f.band === "medium"),
    ).length;

    return { domains, live, families, formats: [...formats], warnings };
  }, [report]);

  return (
    <section aria-label="Run summary" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat value={stats.domains} label="Domains" note={`${stats.live} live`} />
      <Stat value={stats.families} label="Font families" />
      <Stat
        value={stats.formats.length}
        label="Font formats"
        note={stats.formats.join(", ") || undefined}
      />
      <Stat value={stats.warnings} label="Warnings" note="open · medium+high" />
    </section>
  );
}
