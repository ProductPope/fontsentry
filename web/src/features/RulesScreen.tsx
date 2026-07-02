import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { Rule, RulesConfig } from "../lib/api";

const TH = "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]";

// Editable subset: weights, confidences, and the band thresholds. A rule's
// condition (predicate type + params) is code-backed vocabulary and stays
// read-only here — tune those in rules.yaml directly.
export function RulesScreen({ notify }: { notify: (message: string, kind: ToastKind) => void }) {
  const [config, setConfig] = useState<RulesConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getRules()
      .then(setConfig)
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load rules", "error"),
      )
      .finally(() => setLoading(false));
  }, [notify]);

  function updateScoring(patch: { max_raw?: number; medium?: number; high?: number }) {
    setConfig((c) =>
      c === null
        ? c
        : {
            ...c,
            scoring: {
              max_raw: patch.max_raw ?? c.scoring.max_raw,
              bands: {
                medium: patch.medium ?? c.scoring.bands.medium,
                high: patch.high ?? c.scoring.bands.high,
              },
            },
          },
    );
  }

  function updateRule(index: number, patch: Partial<Pick<Rule, "weight" | "confidence">>) {
    setConfig((c) =>
      c === null ? c : { ...c, rules: c.rules.map((r, i) => (i === index ? { ...r, ...patch } : r)) },
    );
  }

  async function save() {
    if (config === null) return;
    setSaving(true);
    try {
      const saved = await api.saveRules(config);
      setConfig(saved);
      notify("Saved scoring rules", "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save rules", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">Rules</h2>
        <p className="text-sm text-muted">
          The scoring engine. Each rule that matches a font contributes weight × confidence to its
          raw score; the raw score is normalized against Max raw and mapped to a band by the
          thresholds below. Conditions are code-backed and read-only here.
        </p>
      </div>

      {loading || config === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <Card className="flex flex-wrap items-end gap-4">
            <Num
              label="Max raw"
              value={config.scoring.max_raw}
              min={1}
              onChange={(v) => updateScoring({ max_raw: v })}
            />
            <Num
              label="Medium band ≥"
              value={config.scoring.bands.medium}
              min={0}
              max={100}
              onChange={(v) => updateScoring({ medium: v })}
            />
            <Num
              label="High band ≥"
              value={config.scoring.bands.high}
              min={0}
              max={100}
              onChange={(v) => updateScoring({ high: v })}
            />
          </Card>

          <div className="overflow-x-auto rounded-card border border-stroke">
            <table className="w-full border-collapse bg-surface text-sm">
              <thead>
                <tr className="bg-surface2 text-left text-muted">
                  <th scope="col" className={TH}>
                    Rule
                  </th>
                  <th scope="col" className={TH}>
                    Condition
                  </th>
                  <th scope="col" className={`${TH} w-28`}>
                    Weight
                  </th>
                  <th scope="col" className={`${TH} w-32`}>
                    Confidence
                  </th>
                </tr>
              </thead>
              <tbody>
                {config.rules.map((r, i) => (
                  <tr key={r.id} className="border-t border-stroke align-top">
                    <td className="px-4 py-2">
                      <div className="font-medium">{r.id}</div>
                      {r.description && (
                        <div className="mt-0.5 text-xs text-muted">{r.description}</div>
                      )}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-muted">{r.when.type}</td>
                    <td className="px-4 py-2">
                      <TextInput
                        aria-label={`Weight for ${r.id}`}
                        type="number"
                        min={0}
                        value={r.weight}
                        onChange={(e) => updateRule(i, { weight: Number(e.target.value) })}
                      />
                    </td>
                    <td className="px-4 py-2">
                      <TextInput
                        aria-label={`Confidence for ${r.id}`}
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        value={r.confidence}
                        onChange={(e) => updateRule(i, { confidence: Number(e.target.value) })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save rules"}
          </Button>
        </>
      )}
    </section>
  );
}

function Num({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <TextInput
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32 font-mono"
      />
    </label>
  );
}
