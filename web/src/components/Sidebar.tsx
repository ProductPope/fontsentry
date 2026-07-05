import { useEffect, useRef } from "react";
import { cn } from "../lib/cn";
import type { Route } from "../lib/useHashRoute";
import { ThemeToggle } from "./ThemeToggle";

const NAV: { id: Route; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "audits", label: "Audits" },
  { id: "registry", label: "Registry" },
  { id: "targets", label: "Targets" },
  { id: "rules", label: "Rules" },
  { id: "how-it-works", label: "How it works" },
];

export function Sidebar({
  route,
  onNavigate,
  open,
  onClose,
}: {
  route: Route;
  onNavigate: (route: Route) => void;
  open: boolean;
  onClose: () => void;
}) {
  const asideRef = useRef<HTMLElement>(null);

  // Mobile drawer only (`open` is never set on desktop): on open, move focus into
  // the drawer and let Escape close it (WCAG 2.1.1 / 2.4.3).
  useEffect(() => {
    if (!open) return;
    asideRef.current?.querySelector<HTMLElement>("button, [href]")?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* Off-canvas backdrop (mobile only, when open). */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        ref={asideRef}
        id="app-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-screen w-64 flex-col border-r border-stroke bg-surface",
          "transition-transform md:sticky md:top-0 md:z-auto md:w-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="border-b border-stroke px-5 pb-4 pt-5">
          <div className="text-lg font-bold">FontSentry</div>
          <div className="text-xs text-muted">heuristic estimate · not legal advice</div>
        </div>
        <nav className="flex-1 space-y-1 p-3" aria-label="Sections">
          {NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              onClick={() => {
                onNavigate(n.id);
                onClose();
              }}
              aria-current={route === n.id ? "page" : undefined}
              className={cn(
                "block w-full rounded-tk px-3 py-2 text-left text-sm font-medium transition-colors",
                route === n.id
                  ? "bg-accent-soft text-accent"
                  : "text-muted hover:bg-surface2 hover:text-ink",
              )}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className="flex items-center justify-between border-t border-stroke p-3">
          <span className="text-xs text-muted">Theme</span>
          <ThemeToggle />
        </div>
      </aside>
    </>
  );
}
