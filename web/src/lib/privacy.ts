// Presentation helpers for the privacy (delivery) axis. The backend classifies
// each finding as self-hosted / third-party / mixed; here we turn that into a
// human label, an amber/green tone, and a GDPR recommendation. The specific
// provider (Google Fonts, Adobe…) comes from the embeddings already on the
// finding — the privacy axis is independent of the license band.

import type { Finding } from "./api";

export interface Delivery {
  label: string;
  flagged: boolean; // true => third-party delivery (a privacy concern)
}

function provider(f: Finding): string {
  if (f.embeddings.includes("google_fonts")) return "Google Fonts (API)";
  if (f.embeddings.includes("adobe_fonts")) return "Adobe Fonts";
  if (f.embeddings.includes("monotype")) return "Monotype";
  return "3rd-party CDN";
}

export function delivery(f: Finding): Delivery {
  switch (f.privacy) {
    case "self_hosted":
      return { label: "Self-hosted", flagged: false };
    case "third_party_api":
      return { label: provider(f), flagged: true };
    case "mixed":
      return { label: `${provider(f)} + self-hosted`, flagged: true };
    default:
      return { label: "System", flagged: false };
  }
}

// A font is a privacy concern when any of its delivery is third-party.
export function isPrivacyFlagged(f: Finding): boolean {
  return f.privacy === "third_party_api" || f.privacy === "mixed";
}

// Worth the operator's attention: an open license concern (medium+ and not
// already covered by the registry) OR a privacy concern. Open/free low-risk
// fonts fall out of this — that's the default "ignore free licenses" view.
export function needsAction(f: Finding): boolean {
  const licenseConcern = f.status === "open" && f.band !== "low";
  return licenseConcern || isPrivacyFlagged(f);
}

// Plain-language GDPR/RODO recommendation, or null when delivery is clean.
export function privacyAdvice(f: Finding): string | null {
  if (!isPrivacyFlagged(f)) return null;
  if (f.embeddings.includes("google_fonts")) {
    return (
      "Privacy (GDPR/RODO): this font loads from Google's servers, which sends every " +
      "visitor's IP address to Google. Self-host the font files to stay compliant."
    );
  }
  const who = provider(f);
  const base =
    `Privacy (GDPR/RODO): this font loads from a third party (${who}), sending visitor ` +
    "data off-site. Consider self-hosting the font files.";
  return f.privacy === "mixed"
    ? base + " It is already self-hosted on some pages — move the rest over too."
    : base;
}
