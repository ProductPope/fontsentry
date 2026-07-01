import type { HTMLAttributes } from "react";
import { cn } from "../lib/cn";

export type Band = "low" | "medium" | "high";

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

const bandStyles: Record<Band, string> = {
  low: "bg-band-low-bg text-band-low border-band-low-line",
  medium: "bg-band-medium-bg text-band-medium border-band-medium-line",
  high: "bg-band-high-bg text-band-high border-band-high-line",
};

export function RiskBadge({ band }: { band: Band }) {
  return (
    <Badge className={bandStyles[band]} aria-label={`risk band ${band}`}>
      {band}
    </Badge>
  );
}

// Finding status is auto-computed, not a badge in the comp — rendered as a
// subtly-coloured label: resolved (a matched license) reads calm/green, open
// stays muted.
export function StatusText({ status }: { status: string }) {
  return (
    <span className={cn("font-medium", status === "resolved" ? "text-band-low" : "text-muted")}>
      {status}
    </span>
  );
}
