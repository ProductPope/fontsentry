import { useCallback, useSyncExternalStore } from "react";

// Minimal dependency-free hash router. The app is a small local tool, so a full
// router library would be overkill; sections live at #/overview, #/audits, etc.

export const ROUTES = [
  "overview",
  "audits",
  "registry",
  "targets",
  "rules",
  "backup",
  "how-it-works",
] as const;
export type Route = (typeof ROUTES)[number];

function currentRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return (ROUTES as readonly string[]).includes(hash) ? (hash as Route) : "overview";
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

export function useHashRoute(): { route: Route; navigate: (route: Route) => void } {
  const route = useSyncExternalStore(subscribe, currentRoute, (): Route => "overview");
  const navigate = useCallback((next: Route) => {
    window.location.hash = `/${next}`;
  }, []);
  return { route, navigate };
}
