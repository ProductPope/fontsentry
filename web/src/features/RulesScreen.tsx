import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { RulesConfig } from "../lib/api";

const toLines = (xs: string[]) => xs.join("\n");
const fromLines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

// Editable classification data (ADR 0003): the deterministic engine reads these
// lists — no weights or thresholds. Structured lists (open_families,
// paid_tier_families) stay read-only here; edit those in rules.yaml.
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

  function patch(update: Partial<RulesConfig>) {
    setConfig((c) => (c === null ? c : { ...c, ...update }));
  }

  async function save() {
    if (config === null) return;
    setSaving(true);
    try {
      const saved = await api.saveRules(config);
      setConfig(saved);
      notify("Saved classification config", "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save rules", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">Classification</h2>
        <p className="text-sm text-muted">
          The deterministic verdict engine. These lists decide when a font is provably OK, a
          definite violation, or worth a check. No weights or scores — see{" "}
          <span className="font-mono">docs/rules.md</span> for the decision order.
        </p>
      </div>

      {loading || config === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <Card className="grid gap-5 sm:grid-cols-2">
            <ListField
              label="Open license patterns"
              hint="Substrings in the font's license/copyright → OK"
              value={config.open_license_patterns}
              onChange={(v) => patch({ open_license_patterns: v })}
            />
            <ListField
              label="Free owners"
              hint="Foundries whose fonts are free → OK"
              value={config.free_owners}
              onChange={(v) => patch({ free_owners: v })}
            />
            <ListField
              label="Self-host prohibited — owners"
              hint="Self-hosting these owners → Violation"
              value={config.self_host_prohibited.owners}
              onChange={(v) =>
                patch({ self_host_prohibited: { ...config.self_host_prohibited, owners: v } })
              }
            />
            <ListField
              label="Self-host prohibited — families"
              hint="Self-hosting these families → Violation"
              value={config.self_host_prohibited.families}
              onChange={(v) =>
                patch({ self_host_prohibited: { ...config.self_host_prohibited, families: v } })
              }
            />
            <ListField
              label="Paid CDNs (evidence)"
              hint="Embedding methods, e.g. adobe_fonts"
              value={config.paid_cdns}
              onChange={(v) => patch({ paid_cdns: v })}
            />
            <ListField
              label="Desktop formats (evidence)"
              hint="Formats rarely licensed for the web, e.g. ttf, otf"
              value={config.desktop_formats}
              onChange={(v) => patch({ desktop_formats: v })}
            />
          </Card>

          <Card className="flex flex-wrap items-end gap-4">
            <label className="text-sm">
              <span className="mb-1 block font-medium">Subset max glyphs (evidence)</span>
              <TextInput
                type="number"
                min={0}
                value={config.subset_max_glyphs}
                onChange={(e) => patch({ subset_max_glyphs: Number(e.target.value) })}
                className="w-32 font-mono"
              />
            </label>
            <p className="text-xs text-muted">
              Structured lists (open families, paid-tier families) are edited in{" "}
              <span className="font-mono">rules.yaml</span>.
            </p>
          </Card>

          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save classification"}
          </Button>
        </>
      )}
    </section>
  );
}

function ListField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string[];
  onChange: (value: string[]) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <textarea
        value={toLines(value)}
        onChange={(e) => onChange(fromLines(e.target.value))}
        rows={4}
        className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-xs text-ink"
      />
      <span className="mt-1 block text-xs text-faint">{hint} · one per line</span>
    </label>
  );
}
