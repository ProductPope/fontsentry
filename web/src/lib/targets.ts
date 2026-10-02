// Pure logic for the Targets screen: the domain list is edited as text, one
// domain per line. No React here.
import type { Target } from "./api";

export function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

// Mirror the backend Target.domain validator (models.py) so preserved
// subdomain_seeds are keyed identically on both sides.
export function normalizeDomain(value: string): string {
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
export function parseCsvDomains(text: string): string[] {
  return splitLines(text)
    .map((line) => normalizeDomain(line.split(",")[0] ?? ""))
    .filter((d) => d && d !== "domain");
}

// Append imported domains that aren't already listed; returns the new text and
// how many were added.
export function mergeDomains(text: string, imported: string[]): { text: string; added: number } {
  const existing = splitLines(text);
  const seen = new Set(existing.map(normalizeDomain));
  const added = imported.filter((d) => !seen.has(d));
  return { text: [...existing, ...added].join("\n"), added: added.length };
}

// Targets to save from the edited text. Each domain's subdomain_seeds aren't
// editable here, so they're carried over from the loaded config.
export function targetsFromText(text: string, loaded: Target[]): Target[] {
  const seedsByDomain = new Map(loaded.map((t) => [normalizeDomain(t.domain), t.subdomain_seeds]));
  return splitLines(text).map((domain) => ({
    domain,
    subdomain_seeds: seedsByDomain.get(normalizeDomain(domain)) ?? [],
  }));
}

// Whether the set of domains differs between two target lists.
export function domainsChanged(before: Target[], after: Target[]): boolean {
  const old = new Set(before.map((t) => normalizeDomain(t.domain)));
  const next = after.map((t) => normalizeDomain(t.domain));
  return next.length !== old.size || next.some((d) => !old.has(d));
}

export type LiveStatus = "live" | "unreachable" | "unscanned";

// Each listed domain's reachability in the latest run (unscanned if absent).
export function statusRows(
  text: string,
  liveByDomain: Map<string, boolean>,
): { domain: string; status: LiveStatus }[] {
  return splitLines(text).map((line) => {
    const domain = normalizeDomain(line);
    const live = liveByDomain.get(domain);
    const status: LiveStatus = live === undefined ? "unscanned" : live ? "live" : "unreachable";
    return { domain, status };
  });
}
