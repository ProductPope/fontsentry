import { describe, expect, it } from "vitest";
import {
  domainsChanged,
  mergeDomains,
  normalizeDomain,
  parseCsvDomains,
  statusRows,
  targetsFromText,
} from "./targets";

describe("targets helpers", () => {
  it("normalizes like the backend validator", () => {
    expect(normalizeDomain("  HTTPS://Example.com// ")).toBe("example.com");
    expect(normalizeDomain("http://a.example/")).toBe("a.example");
  });

  it("reads the first CSV column, skipping a header and blanks", () => {
    expect(parseCsvDomains("domain,x\nA.example,1\n\n,2\nb.example\n")).toEqual([
      "a.example",
      "b.example",
    ]);
  });

  it("merges imported domains without duplicates", () => {
    expect(mergeDomains("Example.com\n", ["example.com", "new.example"])).toEqual({
      text: "Example.com\nnew.example",
      added: 1,
    });
  });

  it("carries subdomain seeds over by normalized domain", () => {
    const loaded = [{ domain: "example.com", subdomain_seeds: ["shop"] }];
    expect(targetsFromText("https://EXAMPLE.com\nb.example", loaded)).toEqual([
      { domain: "https://EXAMPLE.com", subdomain_seeds: ["shop"] },
      { domain: "b.example", subdomain_seeds: [] },
    ]);
  });

  it("detects a changed set of domains", () => {
    const t = (domain: string) => ({ domain, subdomain_seeds: [] });
    expect(domainsChanged([t("a.example")], [t("A.example/")])).toBe(false);
    expect(domainsChanged([t("a.example")], [t("b.example")])).toBe(true);
    expect(domainsChanged([t("a.example")], [t("a.example"), t("b.example")])).toBe(true);
  });

  it("reports reachability per listed domain", () => {
    const live = new Map([
      ["a.example", true],
      ["b.example", false],
    ]);
    expect(statusRows("a.example\nb.example\nc.example", live).map((r) => r.status)).toEqual([
      "live",
      "unreachable",
      "unscanned",
    ]);
  });
});
