import { useCallback, useEffect, useState } from "react";
import type { ToastKind } from "../components/Toast";
import { api } from "./api";
import type { RunMeta, RunReport } from "./api";

type Source = "real" | "demo";

// The run list for the active data source and the selected run's report.
// `reload` re-fetches the list (e.g. after a scan finished) even when the
// source didn't change.
export function useRunData(notify: (message: string, kind: ToastKind) => void) {
  const [source, setSource] = useState<Source>("real");
  const [runs, setRuns] = useState<RunMeta[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Keep the current selection if it still exists, otherwise fall back to the
  // newest run.
  useEffect(() => {
    let cancelled = false;
    api
      .getRuns(source)
      .then((list) => {
        if (cancelled) return;
        setRuns(list);
        setSelectedId((prev) => (list.some((r) => r.id === prev) ? prev : list[0]?.id || ""));
      })
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load runs", "error"),
      );
    return () => {
      cancelled = true;
    };
  }, [source, refreshKey, notify]);

  useEffect(() => {
    if (!selectedId) {
      setReport(null);
      return;
    }
    setLoading(true);
    api
      .getRun(selectedId, source)
      .then(setReport)
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load run", "error"),
      )
      .finally(() => setLoading(false));
  }, [selectedId, source, notify]);

  const reload = useCallback(() => setRefreshKey((k) => k + 1), []);

  return { source, setSource, runs, selectedId, setSelectedId, report, loading, reload };
}
