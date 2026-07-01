import { useCallback, useSyncExternalStore } from "react";

// Theme is stored on <html data-theme> (set pre-paint by the inline script in
// index.html) and persisted to localStorage. This hook reads that source of
// truth and lets the UI toggle it.

export type Theme = "light" | "dark";

const STORAGE_KEY = "fontsentry.theme";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures (private mode); the in-DOM theme still applies.
  }
  listeners.forEach((fn) => fn());
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const theme = useSyncExternalStore(subscribe, currentTheme, (): Theme => "light");
  const toggle = useCallback(() => {
    setTheme(currentTheme() === "dark" ? "light" : "dark");
  }, []);
  return { theme, toggle };
}
