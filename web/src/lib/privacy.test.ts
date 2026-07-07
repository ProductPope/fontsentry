import { describe, expect, it } from "vitest";
import type { Finding } from "./api";
import { needsAction } from "./findings";
import { delivery, isPrivacyFlagged, privacyAdvice } from "./privacy";

function finding(over: Partial<Finding> = {}): Finding {
  return {
    family: "Demo",
    family_group: "Demo",
    owner: null,
    domains: ["example.com"],
    formats: ["woff2"],
    embeddings: ["self_hosted"],
    metadata: null,
    license_verdict: "ok",
    license_reason: "",
    evidence_notes: [],
    privacy: "self_hosted",
    registry_match: false,
    example_urls: [],
    page_count: 1,
    applied: true,
    ...over,
  };
}

describe("delivery", () => {
  it("labels a self-hosted font as not flagged", () => {
    expect(delivery(finding({ privacy: "self_hosted" }))).toEqual({
      label: "Self-hosted",
      flagged: false,
    });
  });

  it("names the provider and flags Google Fonts API", () => {
    const d = delivery(finding({ privacy: "third_party_api", embeddings: ["google_fonts"] }));
    expect(d.flagged).toBe(true);
    expect(d.label).toContain("Google Fonts");
  });

  it("marks mixed delivery as flagged", () => {
    const d = delivery(
      finding({ privacy: "mixed", embeddings: ["google_fonts", "self_hosted"] }),
    );
    expect(d.flagged).toBe(true);
    expect(d.label).toContain("self-hosted");
  });

  it("names each third-party provider", () => {
    expect(delivery(finding({ privacy: "third_party_api", embeddings: ["adobe_fonts"] })).label).toBe(
      "Adobe Fonts",
    );
    expect(delivery(finding({ privacy: "third_party_api", embeddings: ["monotype"] })).label).toBe(
      "Monotype",
    );
    expect(delivery(finding({ privacy: "third_party_api", embeddings: ["other_cdn"] })).label).toBe(
      "3rd-party CDN",
    );
  });

  it("labels a system font as not flagged", () => {
    expect(delivery(finding({ privacy: "not_applicable", embeddings: ["system"] }))).toEqual({
      label: "System",
      flagged: false,
    });
  });

  it("labels unobserved delivery as unknown, without a leak claim", () => {
    expect(delivery(finding({ privacy: "unknown", embeddings: ["unknown"] }))).toEqual({
      label: "Unknown delivery",
      flagged: false,
    });
  });
});

describe("isPrivacyFlagged", () => {
  it("is true for third-party and mixed, false otherwise", () => {
    expect(isPrivacyFlagged(finding({ privacy: "third_party_api" }))).toBe(true);
    expect(isPrivacyFlagged(finding({ privacy: "mixed" }))).toBe(true);
    expect(isPrivacyFlagged(finding({ privacy: "self_hosted" }))).toBe(false);
    expect(isPrivacyFlagged(finding({ privacy: "not_applicable" }))).toBe(false);
    expect(isPrivacyFlagged(finding({ privacy: "unknown" }))).toBe(false); // no proven leak
  });
});

describe("privacyAdvice for unknown delivery", () => {
  it("suggests verifying, without claiming a leak", () => {
    const advice = privacyAdvice(finding({ privacy: "unknown", embeddings: ["unknown"] }));
    expect(advice).toContain("not observed");
    expect(advice).not.toContain("GDPR");
  });
});

describe("needsAction", () => {
  it("hides OK/self-hosted, keeps non-OK and privacy-flagged", () => {
    expect(needsAction(finding({ license_verdict: "ok", privacy: "self_hosted" }))).toBe(false);
    expect(needsAction(finding({ license_verdict: "needs_check" }))).toBe(true);
    expect(needsAction(finding({ license_verdict: "violation" }))).toBe(true);
    // OK licence but third-party delivery still needs attention (GDPR).
    expect(needsAction(finding({ license_verdict: "ok", privacy: "third_party_api" }))).toBe(true);
  });
});

describe("privacyAdvice", () => {
  it("gives a GDPR self-hosting recommendation for Google Fonts, null when clean", () => {
    expect(privacyAdvice(finding({ privacy: "third_party_api", embeddings: ["google_fonts"] }))).
      toMatch(/self-host/i);
    expect(privacyAdvice(finding({ privacy: "self_hosted" }))).toBeNull();
  });

  it("advises for a generic third-party and notes the mixed case", () => {
    const generic = privacyAdvice(finding({ privacy: "third_party_api", embeddings: ["monotype"] }));
    expect(generic).toMatch(/third party/i);
    expect(generic).toContain("Monotype");
    const mixed = privacyAdvice(finding({ privacy: "mixed", embeddings: ["adobe_fonts", "self_hosted"] }));
    expect(mixed).toMatch(/already self-hosted/i);
  });
});
