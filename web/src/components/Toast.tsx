import { cn } from "../lib/cn";

export type ToastKind = "info" | "success" | "error";

export interface ToastState {
  message: string;
  kind: ToastKind;
}

const kinds: Record<ToastKind, string> = {
  info: "border-stroke",
  success: "border-band-low",
  error: "border-band-high",
};

export function Toast({ message, kind, onDismiss }: ToastState & { onDismiss: () => void }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-3 rounded-tk border-l-4 bg-surface px-4 py-3 text-sm shadow-lg",
        kinds[kind],
      )}
    >
      <span className="text-ink">{message}</span>
      <button onClick={onDismiss} aria-label="Dismiss notification" className="text-muted">
        ✕
      </button>
    </div>
  );
}
