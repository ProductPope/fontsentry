import { useCallback, useEffect, useState } from "react";
import type { ToastKind, ToastState } from "../components/Toast";

// One toast at a time. Errors stay until dismissed (WCAG 2.2.1);
// info/success auto-dismiss after a few seconds.
export function useToast(): {
  toast: ToastState | null;
  notify: (message: string, kind: ToastKind) => void;
  dismiss: () => void;
} {
  const [toast, setToast] = useState<ToastState | null>(null);

  const notify = useCallback((message: string, kind: ToastKind) => {
    setToast({ message, kind });
  }, []);
  const dismiss = useCallback(() => setToast(null), []);

  useEffect(() => {
    if (!toast || toast.kind === "error") return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  return { toast, notify, dismiss };
}
