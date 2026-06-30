import type { ReactNode } from "react";

// Wrapping the control in a <label> gives an implicit, accessible association.
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}
