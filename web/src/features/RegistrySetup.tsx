import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { KnownFont, RegistryEntry } from "../lib/api";
import { EXAMPLES } from "../lib/registryForm";
import { LicenseCard } from "./LicenseCard";
import { LicenseModal } from "./LicenseModal";
import { RegistryTransfer } from "./RegistryTransfer";

export function RegistrySetup({ notify }: { notify: (message: string, kind: ToastKind) => void }) {
  const [loading, setLoading] = useState(true);
  const [entries, setEntries] = useState<RegistryEntry[]>([]);
  const [knownFonts, setKnownFonts] = useState<KnownFont[]>([]);
  const [busy, setBusy] = useState(false);
  // null = closed; number = editing that index; -1 = adding new.
  const [editing, setEditing] = useState<number | null>(null);

  useEffect(() => {
    api
      .getRegistry()
      .then((r) => setEntries(r.entries))
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load registry", "error"),
      )
      .finally(() => setLoading(false));
  }, [notify]);

  useEffect(() => {
    // Suggestions for the add/edit form; a nice-to-have, so ignore failures.
    api
      .getKnownFonts()
      .then(setKnownFonts)
      .catch(() => {});
  }, []);

  // Single source of persistence: replace the whole registry file, then reflect
  // the server's canonical result. Every add/edit/delete goes through here so
  // there is no separate "Save" step to forget.
  async function persist(next: RegistryEntry[], message: string) {
    setBusy(true);
    try {
      const saved = await api.saveRegistry({ entries: next });
      setEntries(saved.entries);
      notify(message, "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save licenses", "error");
    } finally {
      setBusy(false);
    }
  }

  function commit(entry: RegistryEntry) {
    const next =
      editing === -1 || editing === null
        ? [...entries, entry]
        : entries.map((e, i) => (i === editing ? entry : e));
    setEditing(null);
    void persist(next, "License saved");
  }

  function remove(index: number) {
    void persist(
      entries.filter((_, i) => i !== index),
      "License removed",
    );
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">Registry</h2>
        <p className="text-sm text-muted">
          The font licenses you own. A detected font is marked <strong>resolved</strong> instead of
          an open finding when a license here matches it — same owner and family, the domain is
          allowed, within the domain limit, and not expired.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setEditing(-1)} disabled={busy}>
              Add license
            </Button>
            {entries.length === 0 && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void persist([...entries, ...EXAMPLES], "Example licenses added")}
              >
                Insert examples
              </Button>
            )}
            <RegistryTransfer
              entries={entries}
              busy={busy}
              setBusy={setBusy}
              onImported={setEntries}
              notify={notify}
            />
          </div>

          {entries.length === 0 ? (
            <Card>
              <p className="text-sm text-muted">
                No licenses yet. Add the fonts you have a license for so matching findings resolve
                automatically.
              </p>
            </Card>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {entries.map((e, i) => (
                <LicenseCard
                  key={`${e.owner}::${e.family}::${i}`}
                  entry={e}
                  busy={busy}
                  onEdit={() => setEditing(i)}
                  onDelete={() => remove(i)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {editing !== null && (
        <LicenseModal
          initial={editing >= 0 ? entries[editing]! : null}
          busy={busy}
          knownFonts={knownFonts}
          onCancel={() => setEditing(null)}
          onSave={commit}
          notify={notify}
        />
      )}
    </section>
  );
}
