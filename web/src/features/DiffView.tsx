import { useEffect, useState } from "react";
import { Select } from "../components/Select";
import { api } from "../lib/api";
import type { DiffResult, RunMeta } from "../lib/api";

function DiffCol({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-tk border border-stroke bg-surface p-3">
      <h3 className="mb-2 font-semibold">
        {title} <span className="text-muted">({items.length})</span>
      </h3>
      {items.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {items.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">none</p>
      )}
    </div>
  );
}

export function DiffView({ runs, currentId }: { runs: RunMeta[]; currentId: string }) {
  const others = runs.filter((r) => r.id !== currentId);
  const [prevId, setPrevId] = useState<string>(others[0]?.id ?? "");
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!prevId) {
      setDiff(null);
      return;
    }
    setError(null);
    api
      .getDiff(prevId, currentId)
      .then(setDiff)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "diff failed"));
  }, [prevId, currentId]);

  if (others.length === 0) {
    return <p className="text-muted">Need at least two runs to compare.</p>;
  }

  return (
    <section className="space-y-3">
      <label className="text-sm">
        <span className="mb-1 block font-medium">Compare current with</span>
        <Select value={prevId} onChange={(e) => setPrevId(e.target.value)}>
          {others.map((r) => (
            <option key={r.id} value={r.id}>
              {r.id}
            </option>
          ))}
        </Select>
      </label>
      {error && <p className="text-band-high">{error}</p>}
      {diff && (
        <div className="grid gap-4 sm:grid-cols-3">
          <DiffCol
            title="New"
            items={diff.new_findings.map((f) => `${f.family} (${f.score})`)}
          />
          <DiffCol title="Resolved" items={diff.resolved_findings.map((f) => f.family)} />
          <DiffCol
            title="Changed"
            items={diff.changed.map((d) => `${d.family}: ${d.old_score} → ${d.new_score}`)}
          />
        </div>
      )}
    </section>
  );
}
