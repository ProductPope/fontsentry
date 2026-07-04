// The expandable per-finding detail panel (verdict, privacy advice, why/what/
// where, font metadata). Split out of FindingsTable so the table file stays about
// the table.
import { VerdictBadge } from "../components/Badge";
import type { Finding } from "../lib/api";
import { actionText } from "../lib/findings";
import { delivery, privacyAdvice } from "../lib/privacy";
import { safeHref } from "../lib/url";

export function FindingDetail({ finding }: { finding: Finding }) {
  const m = finding.metadata;
  const advice = privacyAdvice(finding);
  const ok = finding.license_verdict === "ok";

  return (
    <div className="space-y-5 bg-surface2 px-4 py-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <VerdictBadge verdict={finding.license_verdict} />
        <span className="text-muted">{finding.license_reason}</span>
      </div>

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
          so it's a weaker signal. Hosting the file can still be a licensing concern.
        </p>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-4">
          <div>
            <h3 className="mb-1 font-semibold">{ok ? "Why it's cleared" : "Why it's flagged"}</h3>
            <p className={ok ? "text-band-low" : "text-muted"}>{finding.license_reason}</p>
            {finding.evidence_notes.length > 0 && (
              <>
                <div className="mt-2 text-xs uppercase tracking-wide text-faint">
                  What we noticed
                </div>
                <ul className="mt-0.5 list-disc space-y-1 pl-5 text-muted">
                  {finding.evidence_notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </>
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
