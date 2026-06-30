import type { HTMLAttributes } from "react";
import { cn } from "../lib/cn";

export type Band = "low" | "medium" | "high";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2 py-0.5 text-xs font-semibold",
        className,
      )}
      {...props}
    />
  );
}

const bandStyles: Record<Band, string> = {
  low: "bg-band-low text-white",
  medium: "bg-band-medium text-white",
  high: "bg-band-high text-white",
};

export function RiskBadge({ band }: { band: Band }) {
  return (
    <Badge className={bandStyles[band]} aria-label={`risk band ${band}`}>
      {band}
    </Badge>
  );
}
