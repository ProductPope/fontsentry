import type { InputHTMLAttributes } from "react";
import { cn } from "../lib/cn";

export function TextInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-tk border border-stroke bg-surface px-3 py-2 text-sm text-ink",
        className,
      )}
      {...props}
    />
  );
}
