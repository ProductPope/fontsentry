import type { ReactNode } from "react";

interface AppHeaderProps {
  title: string;
  navOpen: boolean;
  onOpenNav: () => void;
  actions: ReactNode;
}

// Sticky page header: mobile menu button, page title, and page-level actions.
export function AppHeader({ title, navOpen, onOpenNav, actions }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-stroke bg-surface/85 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenNav}
            aria-label="Open navigation"
            aria-controls="app-sidebar"
            aria-expanded={navOpen}
            className="-ml-1 rounded-tk p-1 text-muted hover:text-ink md:hidden"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 7h16M4 12h16M4 17h16"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <h1 className="text-lg font-bold">{title}</h1>
        </div>
        <div className="flex items-center gap-2">{actions}</div>
      </div>
    </header>
  );
}
