// The expandable per-finding detail panel (score gauge, privacy advice, why/what/
// where, font metadata, score breakdown). Split out of FindingsTable so the table
// file stays about the table.
import { cn } from "../lib/cn";
import type { Band, Finding } from "../lib/api";
import { delivery, privacyAdvice } from "../lib/privacy";
import { safeHref } from "../lib/url";
import { actionText } from "../lib/findings";

export type Thresholds = { medium: number; high: number } | null;
export type RuleInfo = { id: string; description: string };

const BAND_TEXT: Record<Band, string> = {
  high: "text-band-high",
  medium: "text-band-medium",
  low: "text-band-low",
};

// A 0-100 gauge with the risk bands as coloured zones and a marker at the score.
function ScoreGauge({ score, band, thresholds }: { score: number; band: Band; thresholds: Thresholds }) {
  const pos = Math.min(100, Math.max(0, score));
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className={cn("font-mono text-3xl font-bold tabular-nums", BAND_TEXT[band])}>
          {score}
        </span>
        <span className="text-xs text-faint">/ 100 · {band} risk</span>
      </div>
      <div className="relative mt-2 h-2 w-full max-w-md rounded-full">
        {thresholds ? (
          <div className="flex h-full w-full overflow-hidden rounded-full">
            <div className="h-full bg-band-low-bg" style={{ width: `${thresholds.medium}%` }} />
            <div
              className="h-full bg-band-medium-bg"
              style={{ width: `${Math.max(0, thresholds.high - thresholds.medium)}%` }}
            />
            <div className="h-full bg-band-high-bg" style={{ width: `${Math.max(0, 100 - thresholds.high)}%` }} />
          </div>
        ) : (
          <div className="h-full w-full rounded-full bg-sunken" />
        )}
        <span
          className="absolute top-[-2px] h-3 w-0.5 bg-ink"
          style={{ left: `${pos}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  );
}

export function FindingDetail({
  finding,
  thresholds,
  rules,
}: {
  finding: Finding;
  thresholds: Thresholds;
  rules: RuleInfo[] | null;
}) {
  const m = finding.metadata;
  const resolved = finding.status === "resolved";
  const firedIds = new Set(finding.triggered_rules.map((r) => r.id));
  const didNotApply = (rules ?? []).filter((r) => !firedIds.has(r.id));
  const advice = privacyAdvice(finding);

  return (
    <div className="space-y-5 bg-surface2 px-4 py-4 text-sm">
      <ScoreGauge score={finding.score} band={finding.band} thresholds={thresholds} />

      {advice && (
        <p className="rounded-tk border-l-2 border-band-medium bg-surface px-3 py-2 text-xs text-muted">
          <strong className="text-band-medium">Delivery: {delivery(finding).label}.</strong>{" "}
          {advice}
        </p>
      )}

      {!finding.applied && (
        <p className="rounded-tk bg-surface px-3 py-2 text-xs text-muted">
          <strong>Served but not applied.</strong> This font file is hosted on the site (via
          <code className="mx-1 font-mono">@font-face</code>) but no text on the page renders in it,
          so the score is lowered. Hosting the file can still be a licensing concern.
        </p>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-4">
          <div>
            <h3 className="mb-1 font-semibold">{resolved ? "Why it's cleared" : "Why it's flagged"}</h3>
            {resolved ? (
              <p className="text-band-low">
                {finding.suppression_reason ?? "Covered by a license in your registry."}
              </p>
            ) : finding.triggered_rules.length > 0 ? (
              <ul className="list-disc space-y-1 pl-5 text-muted">
                {finding.triggered_rules.map((r) => (
                  <li key={r.id}>{r.description || r.id}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No specific reasons recorded.</p>
            )}
          </div>
          <div>
            <h3 className="mb-1 font-semibold">What you can do</h3>
            <p className="text-muted">{actionText(finding)}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="mb-1 font-semibold">Where it appears</h3>
            <p className="font-mono text-xs break-words text-muted">
              {finding.domains.join(", ") || "—"}
            </p>
            {finding.example_urls.length > 0 && (
              <div className="mt-1 text-xs text-muted">
                Seen on {finding.page_count} page{finding.page_count === 1 ? "" : "s"}, e.g.:
                <ul className="mt-0.5 space-y-0.5">
                  {finding.example_urls.map((u) =>
                    safeHref(u) ? (
                      <li key={u}>
                        <a
                          href={safeHref(u) ?? undefined}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono break-all text-accent underline"
                        >
                          {u}
                        </a>
                      </li>
                    ) : (
                      <li key={u} className="font-mono break-all">
                        {u}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            )}
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Font details</h3>
            <dl className="space-y-1">
              <Row label="Designer" value={m?.designer ?? "—"} />
              <Row label="Copyright" value={m?.copyright ?? "—"} />
              <Row label="License" value={m?.license_description ?? "—"} />
              <Row label="License URL" value={m?.license_url ?? "—"} />
              <Row label="Unique ID" value={m?.unique_id ?? "—"} />
              <Row label="Glyphs" value={m?.num_glyphs != null ? String(m.num_glyphs) : "—"} />
            </dl>
          </div>
        </div>
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer font-semibold text-muted">
          How the score was reached
        </summary>
        <div className="mt-2 grid gap-4 sm:grid-cols-2">
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-faint">Rules that fired</div>
            {finding.triggered_rules.length > 0 ? (
              <ul className="space-y-1">
                {finding.triggered_rules.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3">
                    <span>{r.description || r.id}</span>
                    <span className="shrink-0 font-mono text-muted">+{Math.round(r.points)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">None.</p>
            )}
          </div>
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-faint">Didn't apply</div>
            {rules === null ? (
              <p className="text-faint">—</p>
            ) : didNotApply.length > 0 ? (
              <ul className="space-y-1 text-faint">
                {didNotApply.map((r) => (
                  <li key={r.id}>{r.description || r.id}</li>
                ))}
              </ul>
            ) : (
              <p className="text-faint">Every rule fired.</p>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-24 shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  );
}
