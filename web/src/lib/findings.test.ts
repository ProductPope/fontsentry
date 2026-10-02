import { describe, expect, it } from "vitest";
import type { Finding } from "./api";
import {
  actionText,
  filterFindings,
  findingKey,
  groupFindings,
  groupKeyOf,
  isSystemOnly,
  worstVerdict,
} from "./findings";

function f(over: Partial<Finding> = {}): Finding {
  return {
    family: "Demo",
    family_group: "Demo",
    owner: null,
    domains: [],
    formats: [],
    embeddings: ["self_hosted"],
    metadata: null,
    license_verdict: "needs_check",
    license_reason: "",
    evidence_notes: [],
    privacy: "self_hosted",
    registry_match: false,
    example_urls: [],
    page_count: 0,
    applied: true,
    ...over,
  };
}

describe("groupKeyOf", () => {
  it("folds spacing/case/punctuation of the base family", () => {
    expect(groupKeyOf(f({ family_group: "Open Sans" }))).toBe("opensans");
    expect(groupKeyOf(f({ family_group: "", family: "OpenSans!" }))).toBe("opensans");
  });
});

describe("findingKey", () => {
  it("combines family and owner", () => {
    expect(findingKey(f({ family: "Roboto", owner: "Google" }))).toBe("Roboto::Google");
    expect(findingKey(f({ family: "Roboto", owner: null }))).toBe("Roboto::");
  });
});

describe("worstVerdict", () => {
  it("returns the most severe verdict", () => {
    expect(
      worstVerdict([
        f({ license_verdict: "ok" }),
        f({ license_verdict: "violation" }),
        f({ license_verdict: "needs_check" }),
      ]),
    ).toBe("violation");
    expect(worstVerdict([f({ license_verdict: "ok" })])).toBe("ok");
  });
});

describe("isSystemOnly", () => {
  it("is true only when every embedding is system", () => {
    expect(isSystemOnly(f({ embeddings: ["system"] }))).toBe(true);
    expect(isSystemOnly(f({ embeddings: ["system", "self_hosted"] }))).toBe(false);
    expect(isSystemOnly(f({ embeddings: [] }))).toBe(false);
  });
});

describe("actionText", () => {
  it("varies by verdict/system", () => {
    expect(actionText(f({ license_verdict: "ok" }))).toMatch(/No action needed/);
    expect(actionText(f({ license_verdict: "violation", license_reason: "expired" }))).toMatch(
      /Confirm the license/,
    );
    expect(actionText(f({ embeddings: ["system"] }))).toMatch(/system \/ fallback/);
    expect(actionText(f({ license_verdict: "needs_check" }))).toMatch(/Registry/);
  });
});

describe("groupFindings", () => {
  it("folds variants into one group and orders by worst verdict", () => {
    const rows = [
      f({ family: "metropolis", family_group: "Metropolis", license_verdict: "violation" }),
      f({ family: "metropolis-bold", family_group: "Metropolis", license_verdict: "ok" }),
      f({ family: "Roboto", family_group: "Roboto", license_verdict: "needs_check" }),
    ];
    const groups = groupFindings(rows, true);
    expect(groups.map((g) => g.label)).toEqual(["Metropolis", "Roboto"]);
    expect(groups[0]!.findings).toHaveLength(2);
    // ascending flips the order (Roboto needs_check vs Metropolis violation)
    expect(groupFindings(rows, false).map((g) => g.label)).toEqual(["Roboto", "Metropolis"]);
  });
});

describe("filterFindings", () => {
  const rows = [
    f({ family: "Okay", license_verdict: "ok" }),
    f({ family: "Bad", license_verdict: "violation", owner: "Acme Type" }),
    f({ family: "Cdn", license_verdict: "ok", privacy: "third_party_api" }),
    f({ family: "Check", license_verdict: "needs_check" }),
  ];
  const all = { focus: "all", verdict: "all", search: "", desc: true } as const;
  const families = (out: Finding[]) => out.map((x) => x.family);

  it("sorts by severity in either direction", () => {
    expect(families(filterFindings(rows, all)).slice(0, 2)).toEqual(["Bad", "Check"]);
    expect(families(filterFindings(rows, { ...all, desc: false })).at(-1)).toBe("Bad");
  });

  it("focuses on findings needing action or flagged for privacy", () => {
    expect(families(filterFindings(rows, { ...all, focus: "privacy" }))).toEqual(["Cdn"]);
    expect(families(filterFindings(rows, { ...all, focus: "action" }))).not.toContain("Okay");
  });

  it("filters by verdict and by family or owner text", () => {
    expect(families(filterFindings(rows, { ...all, verdict: "ok" }))).toEqual(["Okay", "Cdn"]);
    expect(families(filterFindings(rows, { ...all, search: " acme " }))).toEqual(["Bad"]);
    expect(families(filterFindings(rows, { ...all, search: "CHE" }))).toEqual(["Check"]);
  });
});
