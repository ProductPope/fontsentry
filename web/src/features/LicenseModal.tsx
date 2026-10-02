import { useState } from "react";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import { Modal } from "../components/Modal";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import type { KnownFont, RegistryEntry } from "../lib/api";
import { fromForm, isComplete, toForm } from "../lib/registryForm";
import type { FormState } from "../lib/registryForm";
import { LicenseSuggestions } from "./LicenseSuggestions";
import { ProofField } from "./ProofField";

interface LicenseModalProps {
  initial: RegistryEntry | null;
  busy: boolean;
  knownFonts: KnownFont[];
  onCancel: () => void;
  onSave: (entry: RegistryEntry) => void;
  notify: (message: string, kind: ToastKind) => void;
}

// Add/edit one registry entry. Known fonts (detected + catalog) feed autocomplete.
export function LicenseModal({
  initial,
  busy,
  knownFonts,
  onCancel,
  onSave,
  notify,
}: LicenseModalProps) {
  const [f, setF] = useState<FormState>(() => toForm(initial));
  const [error, setError] = useState(false); // required fields missing on submit

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

  function submit() {
    if (!isComplete(f)) {
      setError(true);
      return;
    }
    setError(false);
    onSave(fromForm(f));
  }

  // Shared a11y props for the three required fields.
  const required = (value: string) => ({
    "aria-required": true,
    "aria-invalid": error && !value.trim(),
    "aria-describedby": error ? "license-error" : undefined,
  });

  return (
    <Modal title={initial ? "Edit license" : "Add license"} onClose={onCancel}>
      <LicenseSuggestions knownFonts={knownFonts} />
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
            {...required(f.family)}
          />
        </Field>
        <Field label="Owner (foundry / vendor / service)">
          <TextInput
            list="known-owners"
            value={f.owner}
            onChange={(e) => setF({ ...f, owner: e.target.value })}
            {...required(f.owner)}
          />
        </Field>
        <Field label="License type">
          <TextInput
            list="license-types"
            placeholder="Commercial — per domain"
            value={f.license_type}
            onChange={(e) => setF({ ...f, license_type: e.target.value })}
            {...required(f.license_type)}
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
        <ProofField
          value={f.proof_path}
          onChange={(proof_path) => setF((prev) => ({ ...prev, proof_path }))}
          notify={notify}
        />
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
