import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { cn } from "../lib/cn";
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

// Parse a CSV: take the first column of each row as a domain, skipping a
// "domain" header row. Returns normalized domains.
function parseCsvDomains(text: string): string[] {
  return splitLines(text)
    .map((line) => normalizeDomain(line.split(",")[0] ?? ""))
    .filter((d) => d && d !== "domain");
}

type LiveStatus = "live" | "unreachable" | "unscanned";

const STATUS_TONE: Record<LiveStatus, string> = {
  live: "text-band-low",
  unreachable: "text-band-high",
  unscanned: "text-faint",
};
const STATUS_LABEL: Record<LiveStatus, string> = {
  live: "live",
  unreachable: "unreachable",
  unscanned: "not scanned",
};

interface TargetsSetupProps {
  notify: (message: string, kind: ToastKind) => void;
  onRunAudit: () => void;
  running: boolean;
}

export function TargetsSetup({ notify, onRunAudit, running }: TargetsSetupProps) {
  const [loading, setLoading] = useState(true);
  // Edited as one-per-line text. `loadedTargets` preserves each domain's
  // subdomain_seeds (not editable here) so a save never drops them.
  const [domainsText, setDomainsText] = useState("");
  const [loadedTargets, setLoadedTargets] = useState<Target[]>([]);
  const [saving, setSaving] = useState(false);
  // After a save that changed the list, show a success step with CTAs instead
  // of the editor.
  const [saved, setSaved] = useState(false);
  // Live/unreachable per domain comes from the latest run, not the config.
  const [liveByDomain, setLiveByDomain] = useState<Map<string, boolean>>(new Map());
  const fileRef = useRef<HTMLInputElement>(null);

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

    void api
      .getRuns()
      .then(async (runs) => {
        if (runs.length === 0) return;
        const report = await api.getRun(runs[0]!.id);
        setLiveByDomain(new Map(report.domains.map((d) => [normalizeDomain(d.domain), d.is_live])));
      })
      .catch(() => {
        // status is a nice-to-have; ignore failures
      });
  }, [notify]);

  const statusRows = useMemo(() => {
    return splitLines(domainsText).map((line) => {
      const domain = normalizeDomain(line);
      const live = liveByDomain.get(domain);
      const status: LiveStatus =
        live === undefined ? "unscanned" : live ? "live" : "unreachable";
      return { domain, status };
    });
  }, [domainsText, liveByDomain]);

  async function save() {
    setSaving(true);
    try {
      const before = new Set(loadedTargets.map((t) => normalizeDomain(t.domain)));
      const seedsByDomain = new Map(
        loadedTargets.map((t) => [normalizeDomain(t.domain), t.subdomain_seeds]),
      );
      const targets: Target[] = splitLines(domainsText).map((domain) => ({
        domain,
        subdomain_seeds: seedsByDomain.get(normalizeDomain(domain)) ?? [],
      }));
      const savedTargets = await api.saveTargets({ targets });
      setLoadedTargets(savedTargets.targets);

      // Success step appears whenever the set of domains actually changed.
      const after = savedTargets.targets.map((t) => normalizeDomain(t.domain));
      const changed = after.length !== before.size || after.some((d) => !before.has(d));
      if (changed) {
        setSaved(true);
      } else {
        notify("No changes to save", "info");
      }
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save domains", "error");
    } finally {
      setSaving(false);
    }
  }

  async function importCsv(file: File) {
    const imported = parseCsvDomains(await file.text());
    if (imported.length === 0) {
      notify("No domains found in that CSV", "error");
      return;
    }
    const existing = splitLines(domainsText);
    const seen = new Set(existing.map(normalizeDomain));
    const added = imported.filter((d) => !seen.has(d));
    setDomainsText([...existing, ...added].join("\n"));
    notify(`Imported ${added.length} new domain(s) — review, then Save`, "info");
  }

  if (loading) {
    return (
      <section className="max-w-3xl space-y-3">
        <h2 className="text-base font-semibold">Targets</h2>
        <p className="text-sm text-muted">Loading…</p>
      </section>
    );
  }

  if (saved) {
    const count = loadedTargets.length;
    return (
      <section className="max-w-xl">
        <Card className="space-y-4 text-center">
          <div>
            <div
              className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-band-low-bg text-band-low"
              aria-hidden="true"
            >
              ✓
            </div>
            <h2 className="mt-2 text-base font-semibold">Domains saved</h2>
            <p className="mt-1 text-sm text-muted">
              {count} domain{count === 1 ? "" : "s"} saved to your local config. Run an audit to
              scan them now, or keep editing the list.
            </p>
          </div>
          <div className="flex justify-center gap-2">
            <Button onClick={onRunAudit} disabled={running}>
              {running ? "Auditing…" : "Run audit"}
            </Button>
            <Button variant="secondary" onClick={() => setSaved(false)} disabled={running}>
              Edit domains
            </Button>
          </div>
        </Card>
      </section>
    );
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
      <div className="space-y-4">
        <div className="space-y-2">
          <textarea
            value={domainsText}
            onChange={(e) => setDomainsText(e.target.value)}
            rows={8}
            spellCheck={false}
            aria-label="Domains to scan, one per line"
            placeholder={"example.com\nexample.org"}
            className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-sm text-ink"
          />
          <div className="flex gap-2">
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save domains"}
            </Button>
            <Button variant="secondary" onClick={() => fileRef.current?.click()}>
              Import CSV
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importCsv(file);
                e.target.value = "";
              }}
            />
          </div>
        </div>

        {statusRows.length > 0 && (
          <div className="overflow-x-auto rounded-card border border-stroke">
            <table className="w-full border-collapse bg-surface text-sm">
              <caption className="sr-only">Target reachability in the latest run</caption>
              <thead>
                <tr className="bg-surface2 text-left text-muted">
                  <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]">
                    Domain
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em]">
                    Latest run
                  </th>
                </tr>
              </thead>
              <tbody>
                {statusRows.map((r) => (
                  <tr key={r.domain} className="border-t border-stroke">
                    <td className="px-4 py-2 font-mono text-xs">{r.domain}</td>
                    <td className={cn("px-4 py-2 font-medium", STATUS_TONE[r.status])}>
                      {STATUS_LABEL[r.status]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
