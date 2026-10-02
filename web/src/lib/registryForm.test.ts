import { describe, expect, it } from "vitest";
import type { RegistryEntry } from "./api";
import { expiryBadge, fromForm, isComplete, toForm } from "./registryForm";

const NOW = new Date("2026-06-01T00:00:00").getTime();

describe("expiryBadge", () => {
  it("reads a missing or unparseable date neutrally", () => {
    expect(expiryBadge(null, NOW)).toEqual({ label: "no expiry", tone: "text-muted" });
    expect(expiryBadge("someday", NOW)).toEqual({ label: "someday", tone: "text-muted" });
  });

  it("bands by days left", () => {
    expect(expiryBadge("2026-05-31", NOW).label).toBe("expired");
    expect(expiryBadge("2026-06-20", NOW)).toEqual({
      label: "expires 2026-06-20",
      tone: "text-band-medium",
    });
    expect(expiryBadge("2027-01-01", NOW)).toEqual({
      label: "valid to 2027-01-01",
      tone: "text-band-low",
    });
  });
});

describe("form round trip", () => {
  const entry: RegistryEntry = {
    owner: "Northwind Type",
    family: "Harbor Serif",
    license_type: "Commercial — unlimited",
    allowed_domains: ["a.example", "b.example"],
    max_domains: 2,
    proof_path: "invoice.pdf",
    invoice_path: null,
    valid_until: "2027-12-31",
    notes: "note",
  };

  it("an entry survives toForm → fromForm unchanged", () => {
    expect(fromForm(toForm(entry))).toEqual(entry);
  });

  it("a new form starts empty and incomplete", () => {
    const blank = toForm(null);
    expect(blank.allowedDomainsText).toBe("");
    expect(isComplete(blank)).toBe(false);
  });

  it("trims text and splits the domain list", () => {
    const f = { ...toForm(null), owner: " A ", family: " B ", license_type: " C " };
    f.allowedDomainsText = " x.example , ,y.example ";
    expect(isComplete(f)).toBe(true);
    expect(fromForm(f)).toMatchObject({
      owner: "A",
      family: "B",
      license_type: "C",
      allowed_domains: ["x.example", "y.example"],
    });
  });

  it("whitespace-only required fields are incomplete", () => {
    expect(isComplete({ ...toForm(entry), owner: "  " })).toBe(false);
  });
});
