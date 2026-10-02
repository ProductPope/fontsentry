import { useEffect, useState } from "react";
import { api } from "./api";
import type { DiffResult, RunMeta } from "./api";
import { countByVerdict } from "./overview";
import type { VerdictCounts } from "./overview";

// The selected run compared with the one before it: that run's verdict counts
// (for "vs last run" deltas) and the per-finding diff. Both are null for the
// oldest run or when loading fails. `runs` is newest-first, so the previous run
// is the next index.
export function useRunComparison(
  runs: RunMeta[],
  selectedId: string,
  source: "real" | "demo",
): { prev: VerdictCounts | null; diff: DiffResult | null } {
  const [prev, setPrev] = useState<VerdictCounts | null>(null);
  const [diff, setDiff] = useState<DiffResult | null>(null);

  useEffect(() => {
    const i = runs.findIndex((r) => r.id === selectedId);
    const prevId = i >= 0 ? runs[i + 1]?.id : undefined;
    if (!prevId) {
      setPrev(null);
      setDiff(null);
      return;
    }
    let cancelled = false;
    api
      .getRun(prevId, source)
      .then((rep) => {
        if (!cancelled) setPrev(countByVerdict(rep));
      })
      .catch(() => setPrev(null));
    api
      .getRunDiff(selectedId, source)
      .then((d) => {
        if (!cancelled) setDiff(d);
      })
      .catch(() => setDiff(null));
    return () => {
      cancelled = true;
    };
  }, [runs, selectedId, source]);

  return { prev, diff };
}
