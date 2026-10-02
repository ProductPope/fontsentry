import { useEffect, useMemo, useState } from "react";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { Target } from "../lib/api";
import {
  domainsChanged,
  mergeDomains,
  normalizeDomain,
  parseCsvDomains,
  statusRows,
  targetsFromText,
} from "../lib/targets";
import { TargetStatusTable } from "./TargetStatusTable";
import { TargetsEditor } from "./TargetsEditor";
import { TargetsSaved } from "./TargetsSaved";

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

  const rows = useMemo(() => statusRows(domainsText, liveByDomain), [domainsText, liveByDomain]);

  async function save() {
    setSaving(true);
    try {
      const savedTargets = await api.saveTargets({
        targets: targetsFromText(domainsText, loadedTargets),
      });
      const changed = domainsChanged(loadedTargets, savedTargets.targets);
      setLoadedTargets(savedTargets.targets);
      // Success step appears whenever the set of domains actually changed.
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
    const merged = mergeDomains(domainsText, imported);
    setDomainsText(merged.text);
    notify(`Imported ${merged.added} new domain(s) — review, then Save`, "info");
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
    return (
      <TargetsSaved
        count={loadedTargets.length}
        running={running}
        onRunAudit={onRunAudit}
        onEdit={() => setSaved(false)}
      />
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
        <TargetsEditor
          text={domainsText}
          onText={setDomainsText}
          saving={saving}
          onSave={() => void save()}
          onImportCsv={(file) => void importCsv(file)}
        />

        {rows.length > 0 && <TargetStatusTable rows={rows} />}
      </div>
    </section>
  );
}
