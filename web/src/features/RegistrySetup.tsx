import { useEffect, useState } from "react";
import { Button } from "../components/Button";
import { TextInput } from "../components/TextInput";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { RegistryEntry } from "../lib/api";

// A registry entry plus the raw, comma-separated text the user types into the
// "allowed domains" field. Splitting on every keystroke would fight the user
// (a trailing comma would vanish), so editing state is kept as text and parsed
// only on save.
interface LicenseRow extends RegistryEntry {
  allowedDomainsText: string;
}

const EMPTY_ROW: LicenseRow = {
  owner: "",
  family: "",
  license_type: "",
  allowed_domains: [],
  allowedDomainsText: "",
  max_domains: null,
  proof_path: null,
  invoice_path: null,
  valid_until: null,
  notes: null,
};

// Suggested values offered in the License type field (still free-text).
const LICENSE_TYPES = [
  "Google Fonts — self-hosted (OFL)",
  "Google Fonts — API (OFL)",
  "Commercial — per domain",
  "Commercial — unlimited",
];

// License-table columns and the tooltip explaining each header.
const COLUMNS: { label: string; tip: string; className: string }[] = [
  {
    label: "Owner",
    tip: "Who owns or publishes the font — the foundry, vendor, or service (e.g. Google Fonts). Matched against the font file's manufacturer metadata.",
    className: "p-2 font-medium",
  },
  {
    label: "Font family",
    tip: 'The font family name as it appears in @font-face or the font file (e.g. "Atlas Grotesk Private").',
    className: "p-2 font-medium",
  },
  {
    label: "License type",
    tip: "Free-text label for the kind of license (per-domain, unlimited, OFL…). Suggestions appear as you type; it is not used in scoring.",
    className: "p-2 font-medium",
  },
  {
    label: "Allowed domains",
    tip: "Comma-separated domains this license covers. Use * for any domain (unlimited). A font seen on a domain not listed here surfaces as an open finding.",
    className: "p-2 font-medium",
  },
  {
    label: "Max",
    tip: "Maximum number of domains the license permits. Leave empty for no limit. A font found on more domains than this is flagged (max_domains exceeded).",
    className: "w-20 p-2 font-medium",
  },
  {
    label: "Valid until",
    tip: "License expiry date (YYYY-MM-DD). After this date the font is flagged as expired. Leave empty if the license never expires.",
    className: "w-40 p-2 font-medium",
  },
  {
    label: "Notes",
    tip: "Free-form notes for your own reference. Not used in scoring.",
    className: "p-2 font-medium",
  },
];

// Illustrative rows the user can insert, then edit or remove. Mirrors
// registry/licenses.example.yaml. Font names are invented; "unlimited" means no
// max_domains cap.
const EXAMPLE_ROWS: LicenseRow[] = [
  {
    ...EMPTY_ROW,
    owner: "Google Fonts",
    family: "Beacon Sans",
    license_type: "Google Fonts — self-hosted (OFL)",
    allowed_domains: ["example.com"],
    allowedDomainsText: "example.com",
    notes: "Open license (OFL); self-hosted @font-face.",
  },
  {
    ...EMPTY_ROW,
    owner: "Google Fonts",
    family: "Meadow Text",
    license_type: "Google Fonts — API (OFL)",
    allowed_domains: ["example.com"],
    allowedDomainsText: "example.com",
    notes: "Open license (OFL); loaded via the Google Fonts API.",
  },
  {
    ...EMPTY_ROW,
    owner: "Meridian Letterworks",
    family: "Atlas Grotesk Private",
    license_type: "Commercial — per domain",
    allowed_domains: ["example.com"],
    allowedDomainsText: "example.com",
    max_domains: 1,
    valid_until: "2027-12-31",
    notes: "Annual web license, one domain.",
  },
  {
    ...EMPTY_ROW,
    owner: "Northwind Type",
    family: "Harbor Serif",
    license_type: "Commercial — unlimited",
    allowed_domains: ["*"],
    allowedDomainsText: "*",
    notes: "Perpetual, unlimited web license: any domain (*), no max_domains cap.",
  },
];

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function RegistrySetup({ notify }: { notify: (message: string, kind: ToastKind) => void }) {
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<LicenseRow[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getRegistry()
      .then((registry) => {
        setRows(
          registry.entries.map((e) => ({
            ...e,
            allowedDomainsText: e.allowed_domains.join(", "),
          })),
        );
      })
      .catch((e: unknown) =>
        notify(e instanceof Error ? e.message : "Could not load registry", "error"),
      )
      .finally(() => setLoading(false));
  }, [notify]);

  function updateRow(index: number, patch: Partial<LicenseRow>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  }

  function insertExamples() {
    setRows((prev) => [...prev, ...EXAMPLE_ROWS.map((r) => ({ ...r }))]);
    notify("Inserted example rows — edit or remove, then Save", "info");
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  async function save() {
    // Drop fully-blank rows; the rest must have the three identifying fields.
    const filled = rows.filter(
      (r) => r.owner.trim() || r.family.trim() || r.license_type.trim(),
    );
    const incomplete = filled.find(
      (r) => !r.owner.trim() || !r.family.trim() || !r.license_type.trim(),
    );
    if (incomplete) {
      notify("Each license needs an owner, family, and license type", "error");
      return;
    }

    setSaving(true);
    try {
      const entries: RegistryEntry[] = filled.map(({ allowedDomainsText, ...entry }) => ({
        ...entry,
        owner: entry.owner.trim(),
        family: entry.family.trim(),
        license_type: entry.license_type.trim(),
        allowed_domains: splitList(allowedDomainsText),
      }));
      const saved = await api.saveRegistry({ entries });
      setRows(
        saved.entries.map((e) => ({ ...e, allowedDomainsText: e.allowed_domains.join(", ") })),
      );
      notify(`Saved ${saved.entries.length} license(s)`, "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not save licenses", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">Registry</h2>
        <p className="text-sm text-muted">
          Licenses you own — one row per font license. Declare how each may be used: which domains
          it covers and the maximum number of domains allowed. A matching, in-scope, unexpired
          license marks a detected font as resolved instead of an open finding.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <datalist id="license-types">
            {LICENSE_TYPES.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>

          <div className="overflow-x-auto rounded-card border border-stroke">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-stroke bg-surface2 text-left text-faint">
                  {COLUMNS.map((c) => (
                    <th key={c.label} className={c.className}>
                      <span
                        title={c.tip}
                        className="cursor-help underline decoration-dotted underline-offset-2"
                      >
                        {c.label}
                      </span>
                    </th>
                  ))}
                  <th className="w-10 p-2">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-3 text-center text-muted">
                      No licenses yet. Click <strong>Add license</strong> to define one.
                    </td>
                  </tr>
                ) : (
                  rows.map((row, i) => (
                    <tr key={i} className="border-b border-stroke align-top last:border-0">
                      <td className="p-1">
                        <TextInput
                          aria-label="Owner"
                          value={row.owner}
                          onChange={(e) => updateRow(i, { owner: e.target.value })}
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="Font family"
                          value={row.family}
                          onChange={(e) => updateRow(i, { family: e.target.value })}
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="License type"
                          list="license-types"
                          placeholder="Commercial — per domain"
                          value={row.license_type}
                          onChange={(e) => updateRow(i, { license_type: e.target.value })}
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="Allowed domains, comma-separated"
                          placeholder="example.com, blog.example.com  (or * for any)"
                          value={row.allowedDomainsText}
                          onChange={(e) => updateRow(i, { allowedDomainsText: e.target.value })}
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="Max domains"
                          type="number"
                          min={1}
                          value={row.max_domains ?? ""}
                          onChange={(e) =>
                            updateRow(i, {
                              max_domains: e.target.value ? Number(e.target.value) : null,
                            })
                          }
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="Valid until"
                          type="date"
                          value={row.valid_until ?? ""}
                          onChange={(e) => updateRow(i, { valid_until: e.target.value || null })}
                        />
                      </td>
                      <td className="p-1">
                        <TextInput
                          aria-label="Notes"
                          value={row.notes ?? ""}
                          onChange={(e) => updateRow(i, { notes: e.target.value || null })}
                        />
                      </td>
                      <td className="p-1 text-center">
                        <Button
                          variant="ghost"
                          aria-label="Remove license"
                          className="px-2"
                          onClick={() => removeRow(i)}
                        >
                          ✕
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={addRow}>
              Add license
            </Button>
            <Button variant="ghost" onClick={insertExamples}>
              Insert examples
            </Button>
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save licenses"}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
