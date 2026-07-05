import type { ReactNode } from "react";
import { PrivacyText, VerdictBadge } from "../components/Badge";
import { Card } from "../components/Card";
import { Faq } from "./Faq";

// Read-only explanation of the deterministic decision the engine makes (ADR 0003).
// The mechanics are code-backed and frozen; the editable classification lists live
// on the Rules screen. This page explains, it does not control.
export function HowItWorks() {
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">
        Every font gets two <strong>deterministic verdicts</strong> — a license verdict and a
        privacy verdict — from a fixed decision table (no scores, no weights). Each verdict
        carries an explicit reason, so any result can be traced to a rule you can read here. The
        verdicts are a <strong>deterministic aid, not legal advice</strong>.
      </p>

      <section aria-labelledby="verdicts-heading" className="space-y-3">
        <h2 id="verdicts-heading" className="text-base font-semibold">
          The two verdicts
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Card className="space-y-2">
            <h3 className="text-sm font-semibold">License</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <VerdictBadge verdict="ok" />
                <dd className="text-muted">
                  No action: covered by your registry, provably open, or a system font.
                </dd>
              </div>
              <div className="flex items-start gap-2">
                <VerdictBadge verdict="needs_check" />
                <dd className="text-muted">
                  The honest default — no license on record and not provably open. A human should
                  look; the row lists what we noticed.
                </dd>
              </div>
              <div className="flex items-start gap-2">
                <VerdictBadge verdict="violation" />
                <dd className="text-muted">
                  A definite lapse: an expired or out-of-scope license, a paid tier, a self-host-
                  prohibited font, or embedding forbidden by the font (OS/2 fsType).
                </dd>
              </div>
            </dl>
          </Card>
          <Card className="space-y-2">
            <h3 className="text-sm font-semibold">Privacy (delivery)</h3>
            <p className="text-sm text-muted">
              Independent of the license — how the font reaches visitors:
            </p>
            <ul className="space-y-1 text-sm">
              <li>
                <PrivacyText privacy="self_hosted" /> — served from the site itself; nothing leaks.
              </li>
              <li>
                <PrivacyText privacy="third_party_api" /> — a font CDN (Google/Adobe/…): each
                visitor&apos;s IP is sent off-site (a GDPR/RODO concern, even for free fonts).
              </li>
              <li>
                <PrivacyText privacy="mixed" /> — both, across pages.
              </li>
              <li>
                <PrivacyText privacy="not_applicable" /> — a system/fallback font; nothing is
                fetched.
              </li>
            </ul>
          </Card>
        </div>
      </section>

      <section aria-labelledby="order-heading" className="space-y-3">
        <h2 id="order-heading" className="text-base font-semibold">
          How the license verdict is decided
        </h2>
        <Card>
          <p className="mb-3 text-sm text-muted">
            The engine walks these steps in order — the first match wins:
          </p>
          <ol className="space-y-2 text-sm">
            <Step n={1}>
              A <strong>system / fallback font</strong> (no <code>@font-face</code>, or a{" "}
              <code>local()</code>-only face) → <VerdictBadge verdict="ok" /> — no license question.
            </Step>
            <Step n={2}>
              A <strong>matching registry entry</strong>: valid, in scope, within its domain limit
              → <VerdictBadge verdict="ok" />; but expired, out of scope, or over the limit →{" "}
              <VerdictBadge verdict="violation" />. (A license you declared and let lapse is a
              violation — this precedes the &quot;provably open&quot; check.)
            </Step>
            <Step n={3}>
              No registry cover, but <strong>provably open</strong> — an open-license string
              (OFL/Apache/…), a known open family, or a free foundry → <VerdictBadge verdict="ok" />.
            </Step>
            <Step n={4}>
              No cover and not open, but a <strong>definite problem</strong> — the font&apos;s OS/2
              <code>fsType</code> forbids embedding, a paid tier named in the family, or a
              self-host-prohibited font self-hosted → <VerdictBadge verdict="violation" />.
            </Step>
            <Step n={5}>
              Otherwise → <VerdictBadge verdict="needs_check" />, with the evidence notes below.
            </Step>
          </ol>
        </Card>
      </section>

      <section aria-labelledby="evidence-heading" className="space-y-3">
        <h2 id="evidence-heading" className="text-base font-semibold">
          Evidence notes
        </h2>
        <Card>
          <p className="mb-2 text-sm text-muted">
            Context shown on a <VerdictBadge verdict="needs_check" /> finding. Notes{" "}
            <em>inform</em> — they never by themselves make a verdict:
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            <li>a desktop font format (ttf/otf) is served on the web;</li>
            <li>served from a paid font CDN with no license on record;</li>
            <li>the font file carries no license or copyright string;</li>
            <li>the font looks subsetted (fewer glyphs than a full set);</li>
            <li>served but not applied to any text;</li>
            <li>referenced but its delivery was not observed (may be injected by JavaScript).</li>
          </ul>
          <p className="mt-3 text-xs text-faint">
            The lists these checks use (open-license patterns, free foundries, paid CDNs, …) are
            editable on the <strong>Rules</strong> screen. The decision order above is fixed in
            code.
          </p>
        </Card>
      </section>

      <Faq />
    </div>
  );
}

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface2 text-xs font-semibold text-muted">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}
