// Pure logic for the findings view — extracted from FindingsTable so it can be
// unit-tested without rendering. No React here.
import type { Finding, LicenseVerdict } from "./api";

// Most-attention-worthy first.
const VERDICT_ORDER: Record<LicenseVerdict, number> = { violation: 2, needs_check: 1, ok: 0 };

export interface Group {
  key: string;
  label: string;
  findings: Finding[];
}

/** Space/punctuation/case-insensitive key so `Open Sans` and `OpenSans` fold together. */
export function groupKeyOf(f: Finding): string {
  return (f.family_group || f.family).toLowerCase().replace(/[^a-z0-9]/g, "");
}

/** Identity of a single finding: family + owner. */
export function findingKey(f: Finding): string {
  return `${f.family}::${f.owner ?? ""}`;
}

/** The most severe license verdict across a set of findings. */
export function worstVerdict(findings: Finding[]): LicenseVerdict {
  return findings.reduce<LicenseVerdict>(
    (worst, f) => (VERDICT_ORDER[f.license_verdict] > VERDICT_ORDER[worst] ? f.license_verdict : worst),
    "ok",
  );
}

/** A finding a human should look at: a license concern or a privacy leak. */
export function needsAction(f: Finding): boolean {
  return (
    f.license_verdict !== "ok" || f.privacy === "third_party_api" || f.privacy === "mixed"
  );
}

/** A font referenced only as a system/fallback (never embedded). */
export function isSystemOnly(f: Finding): boolean {
  return f.embeddings.length > 0 && f.embeddings.every((e) => e === "system");
}

/** Plain-language next step for a non-technical operator. */
export function actionText(f: Finding): string {
  if (f.license_verdict === "violation") {
    return `${f.license_reason}. Confirm the license, or record it under Registry if you own one.`;
  }
  if (f.license_verdict === "ok") {
    return "No action needed for licensing — this font is covered or provably open.";
  }
  if (isSystemOnly(f)) {
    return "This is a system / fallback font (not embedded on the page). Usually nothing to do.";
  }
  return (
    "No license on record and not provably open. If you own a license that permits this use, " +
    "add it under Registry — the same owner and font family, plus the domains it covers. On the " +
    "next scan this clears automatically."
  );
}

/** Fold findings into groups by base family, ordered by each group's worst verdict. */
export function groupFindings(rows: Finding[], desc: boolean): Group[] {
  const map = new Map<string, Group>();
  for (const f of rows) {
    const key = groupKeyOf(f);
    const g = map.get(key);
    if (g) g.findings.push(f);
    else map.set(key, { key, label: f.family_group || f.family, findings: [f] });
  }
  const rankOf = (g: Group) => VERDICT_ORDER[worstVerdict(g.findings)];
  return [...map.values()].sort((a, b) => (desc ? rankOf(b) - rankOf(a) : rankOf(a) - rankOf(b)));
}
