import { describe, expect, it } from "vitest";
import type { Finding } from "./api";
import {
  actionText,
  findingKey,
  groupFindings,
  groupKeyOf,
  isSystemOnly,
  worstBand,
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
    score: 10,
    band: "low",
    status: "open",
    triggered_rules: [],
    registry_match: false,
    suppression_reason: null,
    example_urls: [],
    page_count: 0,
    applied: true,
    privacy: "self_hosted",
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

describe("worstBand", () => {
  it("returns the most severe band", () => {
    expect(worstBand([f({ band: "low" }), f({ band: "high" }), f({ band: "medium" })])).toBe("high");
    expect(worstBand([f({ band: "low" })])).toBe("low");
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
  it("varies by status/system", () => {
    expect(actionText(f({ status: "resolved" }))).toMatch(/No action needed/);
    expect(actionText(f({ embeddings: ["system"] }))).toMatch(/system \/ fallback/);
    expect(actionText(f({ status: "open", embeddings: ["self_hosted"] }))).toMatch(/Registry/);
  });
});

describe("groupFindings", () => {
  it("folds variants into one group and orders by top score", () => {
    const rows = [
      f({ family: "metropolis", family_group: "Metropolis", score: 70 }),
      f({ family: "metropolis-bold", family_group: "Metropolis", score: 40 }),
      f({ family: "Roboto", family_group: "Roboto", score: 50 }),
    ];
    const groups = groupFindings(rows, true);
    expect(groups.map((g) => g.label)).toEqual(["Metropolis", "Roboto"]);
    expect(groups[0]!.findings).toHaveLength(2);
    // ascending flips the order (Roboto 50 vs Metropolis top 70)
    expect(groupFindings(rows, false).map((g) => g.label)).toEqual(["Roboto", "Metropolis"]);
  });
});
