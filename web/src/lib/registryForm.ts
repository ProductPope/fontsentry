import type { RegistryEntry } from "./api";

// Suggestions for the license-type field (free text; these are just common ones).
export const LICENSE_TYPES = [
  "Open (OFL) — self-hosted",
  "Open (OFL) — web service",
  "Commercial — per domain",
  "Commercial — unlimited",
];

// Illustrative licenses a first-time user can drop in, then edit or remove.
// Mirrors registry/licenses.example.yaml; names are invented.
export const EXAMPLES: RegistryEntry[] = [
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

// Client-side expiry read for the card badge. `now` is injectable for tests.
export function expiryBadge(
  valid_until: string | null,
  now: number = Date.now(),
): { label: string; tone: string } {
  if (!valid_until) return { label: "no expiry", tone: "text-muted" };
  const when = new Date(`${valid_until}T00:00:00`);
  if (Number.isNaN(when.getTime())) return { label: valid_until, tone: "text-muted" };
  const days = Math.round((when.getTime() - now) / 86_400_000);
  if (days < 0) return { label: "expired", tone: "text-band-high" };
  if (days <= 30) return { label: `expires ${valid_until}`, tone: "text-band-medium" };
  return { label: `valid to ${valid_until}`, tone: "text-band-low" };
}

// The add/edit form's state: an entry with the domain list as editable text.
export interface FormState {
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

export function toForm(entry: RegistryEntry | null): FormState {
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

// Owner, family and license type are required.
export function isComplete(f: FormState): boolean {
  return Boolean(f.owner.trim() && f.family.trim() && f.license_type.trim());
}

function splitList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function fromForm(f: FormState): RegistryEntry {
  return {
    owner: f.owner.trim(),
    family: f.family.trim(),
    license_type: f.license_type.trim(),
    allowed_domains: splitList(f.allowedDomainsText),
    max_domains: f.max_domains,
    valid_until: f.valid_until,
    notes: f.notes,
    proof_path: f.proof_path,
    invoice_path: f.invoice_path,
  };
}
