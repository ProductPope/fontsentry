import type { SelectHTMLAttributes } from "react";
import { cn } from "../lib/cn";

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-tk border border-stroke bg-surface px-3 py-2 text-sm text-ink",
        className,
      )}
      {...props}
    />
  );
}
