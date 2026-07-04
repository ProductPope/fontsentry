import type { HTMLAttributes } from "react";
import type { LicenseVerdict, PrivacyClass } from "../lib/api";
import { cn } from "../lib/cn";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-chip border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.04em]",
        className,
      )}
      {...props}
    />
  );
}

// Verdict colours reuse the risk-band tokens: OK = calm/green, Need check =
// amber, Violation = red.
const verdictStyles: Record<LicenseVerdict, string> = {
  ok: "bg-band-low-bg text-band-low border-band-low-line",
  needs_check: "bg-band-medium-bg text-band-medium border-band-medium-line",
  violation: "bg-band-high-bg text-band-high border-band-high-line",
};

const verdictLabel: Record<LicenseVerdict, string> = {
  ok: "OK",
  needs_check: "Need check",
  violation: "Violation",
};

export function VerdictBadge({ verdict }: { verdict: LicenseVerdict }) {
  return (
    <Badge className={verdictStyles[verdict]} aria-label={`license ${verdictLabel[verdict]}`}>
      {verdictLabel[verdict]}
    </Badge>
  );
}

const privacyLabel: Record<PrivacyClass, string> = {
  self_hosted: "Self-hosted",
  third_party_api: "Third-party",
  mixed: "Mixed",
  not_applicable: "—",
};

// The privacy axis is delivery-based: third-party/mixed leaks visitor IPs (a GDPR
// concern) so it reads with attention; self-hosted/N-A stay muted.
export function PrivacyText({ privacy }: { privacy: PrivacyClass }) {
  const attention = privacy === "third_party_api" || privacy === "mixed";
  return (
    <span className={cn("font-medium", attention ? "text-band-medium" : "text-muted")}>
      {privacyLabel[privacy]}
    </span>
  );
}
