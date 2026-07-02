import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { Target } from "../lib/api";

function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

// Mirror the backend Target.domain validator (models.py) so preserved
// subdomain_seeds are keyed identically on both sides.
function normalizeDomain(value: string): string {
  let v = value.trim().toLowerCase();
  for (const prefix of ["https://", "http://"]) {
    if (v.startsWith(prefix)) {
      v = v.slice(prefix.length);
    }
  }
  return v.replace(/\/+$/, "");
}

export function TargetsSetup({ notify }: { notify: (message: string, kind: ToastKind) => void }) {
  const [loading, setLoading] = useState(true);
  // Edited as one-per-line text. `loadedTargets` preserves each domain's
  // subdomain_seeds (not editable here) so a save never drops them.
  const [domainsText, setDomainsText] = useState("");
  const [loadedTargets, setLoadedTargets] = useState<Target[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getTargets()
      .then((t) => {
        setLoadedTargets(t.targets);
        setDomainsText(t.targets.map((x) => x.domain).join("\n"));
      })
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load targets", "error"),
      )
      .finally(() => setLoading(false));
  }, [notify]);

  async function save() {
    setSaving(true);
    try {
      const seedsByDomain = new Map(
        loadedTargets.map((t) => [normalizeDomain(t.domain), t.subdomain_seeds]),
      );
      const targets: Target[] = splitLines(domainsText).map((domain) => ({
        domain,
        subdomain_seeds: seedsByDomain.get(normalizeDomain(domain)) ?? [],
      }));
      const saved = await api.saveTargets({ targets });
      setLoadedTargets(saved.targets);
      notify(`Saved ${saved.targets.length} domain(s)`, "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save domains", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="max-w-3xl space-y-3">
      <div>
        <h2 className="text-base font-semibold">Targets</h2>
        <p className="text-sm text-muted">
          Domains to scan, one per line. Real domains are written to a local, gitignored file and
          never leave this machine.
        </p>
      </div>
      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <div className="space-y-2">
          <textarea
            value={domainsText}
            onChange={(e) => setDomainsText(e.target.value)}
            rows={8}
            spellCheck={false}
            placeholder={"example.com\nexample.org"}
            className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-sm text-ink"
          />
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save domains"}
          </Button>
        </div>
      )}
    </section>
  );
}
