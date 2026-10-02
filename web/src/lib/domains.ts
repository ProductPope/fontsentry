// Pure logic for the per-host Domains view. No React here.
import type { DomainReport, LicenseVerdict, PrivacyClass } from "./api";

export interface HostRow {
  host: string;
  domain: string;
  isSubdomain: boolean;
  family: string;
  owner: string | null;
  embeddings: string[];
  formats: string[];
  verdict: LicenseVerdict;
  privacy: PrivacyClass;
  assetUrls: string[];
}

// Map key for (domain, family). A NUL separator can't collide with a family
// name (which may contain spaces) or a domain.
export const firstSeenKey = (domain: string, family: string) => `${domain}\u0000${family}`;

// Short label for a font-file URL column: the filename, plus "+N" when a host
// served more than one file for the same font. Full URLs go in the title.
export function assetLabel(urls: string[]): string {
  if (urls.length === 0) return "—";
  const first = urls[0]!.split("?")[0]!.split("/").pop() || urls[0]!;
  return urls.length > 1 ? `${first} +${urls.length - 1}` : first;
}

// One row per (host, font): subdomains become their own rows.
export function toRows(domains: DomainReport[]): HostRow[] {
  const rows: HostRow[] = [];
  for (const d of domains) {
    for (const f of d.fonts) {
      for (const host of f.hosts) {
        rows.push({
          host,
          domain: d.domain,
          isSubdomain: d.subdomains.includes(host),
          family: f.family,
          owner: f.owner,
          embeddings: f.embeddings,
          formats: f.formats,
          verdict: f.license_verdict,
          privacy: f.privacy,
          assetUrls: f.assets.find((a) => a.host === host)?.urls ?? [],
        });
      }
    }
  }
  return rows.sort((a, b) => a.host.localeCompare(b.host) || a.family.localeCompare(b.family));
}
