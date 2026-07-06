import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Field } from "../components/Field";
import { Modal } from "../components/Modal";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { KnownFont, RegistryConfig, RegistryEntry } from "../lib/api";
import { cn } from "../lib/cn";

const LICENSE_TYPES = [
  "Open (OFL) — self-hosted",
  "Open (OFL) — web service",
  "Commercial — per domain",
  "Commercial — unlimited",
];

// Illustrative licenses a first-time user can drop in, then edit or remove.
// Mirrors registry/licenses.example.yaml; names are invented.
const EXAMPLES: RegistryEntry[] = [
  {
    owner: "Public Glyphs Foundation",
    family: "Beacon Sans",
    license_type: "Open (OFL) — self-hosted",
    allowed_domains: ["example.com"],
    max_domains: null,
    proof_path: null,
    invoice_path: null,
    valid_until: null,
    notes: "Open license (OFL); self-hosted @font-face.",
  },
  {
    owner: "Meridian Letterworks",
    family: "Atlas Grotesk Private",
    license_type: "Commercial — per domain",
    allowed_domains: ["example.com"],
    max_domains: 1,
    proof_path: null,
    invoice_path: null,
    valid_until: "2027-12-31",
    notes: "Annual web license, one domain.",
  },
  {
    owner: "Northwind Type",
    family: "Harbor Serif",
    license_type: "Commercial — unlimited",
    allowed_domains: ["*"],
    max_domains: null,
    proof_path: null,
    invoice_path: null,
    valid_until: null,
    notes: "Perpetual, unlimited web license: any domain (*).",
  },
];

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

// Client-side expiry read for the card badge.
function expiryBadge(valid_until: string | null): { label: string; tone: string } {
  if (!valid_until) return { label: "no expiry", tone: "text-muted" };
  const when = new Date(`${valid_until}T00:00:00`);
  if (Number.isNaN(when.getTime())) return { label: valid_until, tone: "text-muted" };
  const days = Math.round((when.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return { label: "expired", tone: "text-band-high" };
  if (days <= 30) return { label: `expires ${valid_until}`, tone: "text-band-medium" };
  return { label: `valid to ${valid_until}`, tone: "text-band-low" };
}

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

  const importRef = useRef<HTMLInputElement>(null);

  function exportRegistry() {
    const blob = new Blob([JSON.stringify({ entries }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fontsentry-registry.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  // Import merges by owner+family on the server (never deletes), so re-importing a
  // backup onto a machine with existing licenses is safe. Proofs are files, not
  // rows — they are not carried in the JSON and stay under registry/proofs/.
  async function importRegistry(file: File) {
    setBusy(true);
    try {
      const parsed = JSON.parse(await file.text()) as RegistryConfig;
      const saved = await api.importRegistry(parsed);
      setEntries(saved.entries);
      notify(`Imported — ${saved.entries.length} licenses total`, "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Import failed — expected a registry JSON", "error");
    } finally {
      setBusy(false);
    }
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
            <Button
              variant="secondary"
              disabled={busy || entries.length === 0}
              onClick={exportRegistry}
            >
              Export JSON
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => importRef.current?.click()}>
              Import JSON
            </Button>
            <input
              ref={importRef}
              type="file"
              accept="application/json,.json"
              aria-label="Import registry JSON file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = ""; // allow re-selecting the same file
                if (file) void importRegistry(file);
              }}
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
              {entries.map((e, i) => {
                const badge = expiryBadge(e.valid_until);
                return (
                  <Card key={`${e.owner}::${e.family}::${i}`} className="flex flex-col gap-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate font-semibold">{e.family || "—"}</div>
                        <div className="truncate text-sm text-muted">{e.owner || "—"}</div>
                      </div>
                      <span className={cn("shrink-0 text-xs font-medium", badge.tone)}>
                        {badge.label}
                      </span>
                    </div>
                    {e.license_type && <div className="text-sm text-muted">{e.license_type}</div>}
                    <dl className="space-y-1 text-sm">
                      <Line label="Domains">
                        <span className="font-mono text-xs">
                          {e.allowed_domains.includes("*")
                            ? "any domain"
                            : e.allowed_domains.join(", ") || "—"}
                        </span>
                      </Line>
                      {e.max_domains != null && (
                        <Line label="Max">
                          <span className="font-mono">{e.max_domains}</span>
                        </Line>
                      )}
                      {e.proof_path && (
                        <Line label="Proof">
                          <a
                            href={api.proofUrl(e.proof_path)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent underline"
                          >
                            {e.proof_path}
                          </a>
                        </Line>
                      )}
                      {e.notes && <Line label="Notes">{e.notes}</Line>}
                    </dl>
                    <div className="mt-auto flex gap-2 pt-1">
                      <Button variant="secondary" onClick={() => setEditing(i)} disabled={busy}>
                        Edit
                      </Button>
                      <Button variant="ghost" onClick={() => remove(i)} disabled={busy}>
                        Delete
                      </Button>
                    </div>
                  </Card>
                );
              })}
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

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-20 shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

interface FormState {
  owner: string;
  family: string;
  license_type: string;
  allowedDomainsText: string;
  max_domains: number | null;
  valid_until: string | null;
  notes: string | null;
  proof_path: string | null;
  invoice_path: string | null;
}

function toForm(entry: RegistryEntry | null): FormState {
  return {
    owner: entry?.owner ?? "",
    family: entry?.family ?? "",
    license_type: entry?.license_type ?? "",
    allowedDomainsText: entry?.allowed_domains.join(", ") ?? "",
    max_domains: entry?.max_domains ?? null,
    valid_until: entry?.valid_until ?? null,
    notes: entry?.notes ?? null,
    proof_path: entry?.proof_path ?? null,
    invoice_path: entry?.invoice_path ?? null,
  };
}

function LicenseModal({
  initial,
  busy,
  knownFonts,
  onCancel,
  onSave,
  notify,
}: {
  initial: RegistryEntry | null;
  busy: boolean;
  knownFonts: KnownFont[];
  onCancel: () => void;
  onSave: (entry: RegistryEntry) => void;
  notify: (message: string, kind: ToastKind) => void;
}) {
  const [f, setF] = useState<FormState>(() => toForm(initial));
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(false); // required fields missing on submit
  const fileRef = useRef<HTMLInputElement>(null);

  const owners = [...new Set(knownFonts.map((k) => k.owner).filter((o): o is string => !!o))].sort();

  // Picking a known family fills the owner from its metadata when owner is empty
  // — so the two fields stay consistent and typos don't slip in.
  function onFamily(family: string) {
    const match = knownFonts.find((k) => k.family.toLowerCase() === family.trim().toLowerCase());
    setF((prev) => ({
      ...prev,
      family,
      owner: prev.owner.trim() ? prev.owner : (match?.owner ?? ""),
    }));
  }

  async function onProof(file: File) {
    setUploading(true);
    try {
      const { name } = await api.uploadProof(file);
      setF((prev) => ({ ...prev, proof_path: name }));
      notify("Proof attached", "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not upload proof", "error");
    } finally {
      setUploading(false);
    }
  }

  function submit() {
    if (!f.owner.trim() || !f.family.trim() || !f.license_type.trim()) {
      setError(true);
      return;
    }
    setError(false);
    onSave({
      owner: f.owner.trim(),
      family: f.family.trim(),
      license_type: f.license_type.trim(),
      allowed_domains: splitList(f.allowedDomainsText),
      max_domains: f.max_domains,
      valid_until: f.valid_until,
      notes: f.notes,
      proof_path: f.proof_path,
      invoice_path: f.invoice_path,
    });
  }

  return (
    <Modal title={initial ? "Edit license" : "Add license"} onClose={onCancel}>
      <datalist id="license-types">
        {LICENSE_TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <datalist id="known-families">
        {knownFonts.map((k) => (
          <option key={k.family} value={k.family} />
        ))}
      </datalist>
      <datalist id="known-owners">
        {owners.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
      <div className="space-y-3">
        {error && (
          <p id="license-error" role="alert" className="text-sm font-medium text-band-high">
            A license needs an owner, font family, and license type.
          </p>
        )}
        <Field label="Font family">
          <TextInput
            list="known-families"
            placeholder="start typing — pick a detected or well-known font"
            value={f.family}
            onChange={(e) => onFamily(e.target.value)}
            aria-required="true"
            aria-invalid={error && !f.family.trim()}
            aria-describedby={error ? "license-error" : undefined}
          />
        </Field>
        <Field label="Owner (foundry / vendor / service)">
          <TextInput
            list="known-owners"
            value={f.owner}
            onChange={(e) => setF({ ...f, owner: e.target.value })}
            aria-required="true"
            aria-invalid={error && !f.owner.trim()}
            aria-describedby={error ? "license-error" : undefined}
          />
        </Field>
        <Field label="License type">
          <TextInput
            list="license-types"
            placeholder="Commercial — per domain"
            value={f.license_type}
            onChange={(e) => setF({ ...f, license_type: e.target.value })}
            aria-required="true"
            aria-invalid={error && !f.license_type.trim()}
            aria-describedby={error ? "license-error" : undefined}
          />
        </Field>
        <Field label="Allowed domains (comma-separated, or * for any)">
          <TextInput
            placeholder="example.com, blog.example.com"
            value={f.allowedDomainsText}
            onChange={(e) => setF({ ...f, allowedDomainsText: e.target.value })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Max domains (blank = no limit)">
            <TextInput
              type="number"
              min={1}
              value={f.max_domains ?? ""}
              onChange={(e) =>
                setF({ ...f, max_domains: e.target.value ? Number(e.target.value) : null })
              }
            />
          </Field>
          <Field label="Valid until (blank = never)">
            <TextInput
              type="date"
              value={f.valid_until ?? ""}
              onChange={(e) => setF({ ...f, valid_until: e.target.value || null })}
            />
          </Field>
        </div>
        <Field label="Notes">
          <TextInput
            value={f.notes ?? ""}
            onChange={(e) => setF({ ...f, notes: e.target.value || null })}
          />
        </Field>
        <Field label="Proof (PDF or image, optional)">
          {f.proof_path ? (
            <div className="flex items-center gap-2 text-sm">
              <a
                href={api.proofUrl(f.proof_path)}
                target="_blank"
                rel="noreferrer"
                className="min-w-0 truncate text-accent underline"
              >
                {f.proof_path}
              </a>
              <Button
                variant="ghost"
                className="px-2"
                onClick={() => setF({ ...f, proof_path: null })}
              >
                Remove
              </Button>
            </div>
          ) : (
            <>
              <Button
                variant="secondary"
                disabled={uploading}
                onClick={() => fileRef.current?.click()}
              >
                {uploading ? "Uploading…" : "Attach file"}
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onProof(file);
                  e.target.value = "";
                }}
              />
            </>
          )}
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy}>
            {busy ? "Saving…" : "Save license"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
