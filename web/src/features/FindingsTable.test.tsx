import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Finding } from "../lib/api";
import { FindingsTable } from "./FindingsTable";

// The component fetches rule thresholds on mount; keep it offline. A rejected
// promise is handled internally (gauge/breakdown degrade), which is all we need.
vi.mock("../lib/api", () => ({
  api: { getRules: () => Promise.reject(new Error("offline")) },
}));

function finding(over: Partial<Finding> = {}): Finding {
  return {
    family: "Demo",
    family_group: "Demo",
    owner: "Acme",
    domains: ["example.com"],
    formats: ["woff2"],
    embeddings: ["self_hosted"],
    metadata: null,
    score: 40,
    band: "medium",
    status: "open",
    triggered_rules: [],
    registry_match: false,
    suppression_reason: null,
    example_urls: [],
    page_count: 1,
    applied: true,
    privacy: "self_hosted",
    ...over,
  };
}

const FINDINGS: Finding[] = [
  finding({ family: "metropolis", family_group: "Metropolis", band: "high", score: 70 }),
  finding({ family: "metropolis-bold", family_group: "Metropolis", band: "medium", score: 40 }),
  finding({
    family: "Roboto",
    family_group: "Roboto",
    band: "low",
    score: 8,
    privacy: "third_party_api",
    embeddings: ["google_fonts"],
  }),
  finding({
    family: "Ignored",
    family_group: "Ignored",
    band: "low",
    score: 5,
    status: "resolved",
    privacy: "self_hosted",
  }),
];

describe("FindingsTable", () => {
  it("folds family variants into one expandable group row", () => {
    render(<FindingsTable findings={FINDINGS} />);
    // metropolis + metropolis-bold -> one "Metropolis" group with 2 variants.
    expect(screen.getByText("Metropolis")).toBeInTheDocument();
    expect(screen.getByText(/2 variants/)).toBeInTheDocument();
    // Variant rows are hidden until the group is expanded.
    expect(screen.queryByText("metropolis-bold")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Metropolis/ }));
    expect(screen.getByText("metropolis-bold")).toBeInTheDocument();
  });

  it("defaults to 'Needs action': hides resolved low, keeps privacy-flagged low", () => {
    render(<FindingsTable findings={FINDINGS} />);
    // Roboto is low licence risk but third-party (GDPR) -> still shown.
    expect(screen.getByText("Roboto")).toBeInTheDocument();
    // Ignored is low + resolved + self-hosted -> not actionable -> hidden.
    expect(screen.queryByText("Ignored")).not.toBeInTheDocument();
    // Switching to "All" reveals it.
    fireEvent.click(screen.getByRole("button", { name: /^All$/ }));
    expect(screen.getByText("Ignored")).toBeInTheDocument();
  });

  it("exposes sort state and a screen-reader label for flagged delivery", () => {
    render(<FindingsTable findings={FINDINGS} />);
    const scoreHeader = screen.getByRole("columnheader", { name: /score/i });
    expect(scoreHeader).toHaveAttribute("aria-sort");
    // Third-party delivery carries text, not colour/glyph alone.
    expect(screen.getByText(/privacy concern/i)).toBeInTheDocument();
  });
});
