// Pure logic for the findings view — extracted from FindingsTable so it can be
// unit-tested without rendering. No React here.
import type { Band, Finding } from "./api";

const BAND_ORDER: Record<Band, number> = { low: 0, medium: 1, high: 2 };

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

/** The most severe band across a set of findings. */
export function worstBand(findings: Finding[]): Band {
  return findings.reduce<Band>(
    (worst, f) => (BAND_ORDER[f.band] > BAND_ORDER[worst] ? f.band : worst),
    "low",
  );
}

/** A font referenced only as a system/fallback (never embedded). */
export function isSystemOnly(f: Finding): boolean {
  return f.embeddings.length > 0 && f.embeddings.every((e) => e === "system");
}

/** Plain-language next step for a non-technical operator. */
export function actionText(f: Finding): string {
  if (f.status === "resolved") {
    return "No action needed — a matching license in your Registry already covers this.";
  }
  if (isSystemOnly(f)) {
    return "This is a system / fallback font (not embedded on the page). Usually nothing to do.";
  }
  return (
    "If you own a license that permits this use, add it under Registry — the same owner and " +
    "font family, plus the domains it covers. On the next scan this clears automatically."
  );
}

/** Fold findings into groups by base family, ordered by each group's top score. */
export function groupFindings(rows: Finding[], desc: boolean): Group[] {
  const map = new Map<string, Group>();
  for (const f of rows) {
    const key = groupKeyOf(f);
    const g = map.get(key);
    if (g) g.findings.push(f);
    else map.set(key, { key, label: f.family_group || f.family, findings: [f] });
  }
  const scoreOf = (g: Group) => Math.max(...g.findings.map((f) => f.score));
  return [...map.values()].sort((a, b) => (desc ? scoreOf(b) - scoreOf(a) : scoreOf(a) - scoreOf(b)));
}
