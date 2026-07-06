import { describe, expect, it } from "vitest";

import type { RegistryImportResult } from "./api";
import { importSummary } from "./importSummary";

function result(added: number, replaced: number, total: number): RegistryImportResult {
  return {
    registry: {
      entries: Array.from({ length: total }, (_, i) => ({
        owner: `Owner ${i}`,
        family: `Family ${i}`,
        license_type: "Web",
        allowed_domains: [],
        max_domains: null,
        proof_path: null,
        invoice_path: null,
        valid_until: null,
        notes: null,
      })),
    },
    errors: [],
    added,
    replaced,
  };
}

describe("importSummary", () => {
  it("names added and replaced counts and the new total", () => {
    expect(importSummary(result(2, 1, 5))).toBe("Imported — 2 added, 1 replaced; 5 licenses total");
  });

  it("keeps replacements visible even when zero were added", () => {
    // A replacement can silently loosen an entry, so it must always be named.
    expect(importSummary(result(0, 3, 3))).toContain("3 replaced");
  });
});
