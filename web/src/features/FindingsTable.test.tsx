import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Finding } from "../lib/api";
import { FindingsTable } from "./FindingsTable";

function finding(over: Partial<Finding> = {}): Finding {
  return {
    family: "Demo",
    family_group: "Demo",
    owner: "Acme",
    domains: ["example.com"],
    formats: ["woff2"],
    embeddings: ["self_hosted"],
    metadata: null,
    license_verdict: "needs_check",
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

const FINDINGS: Finding[] = [
  finding({ family: "metropolis", family_group: "Metropolis", license_verdict: "violation" }),
  finding({ family: "metropolis-bold", family_group: "Metropolis", license_verdict: "needs_check" }),
  finding({
    family: "Roboto",
    family_group: "Roboto",
    license_verdict: "ok",
    privacy: "third_party_api",
    embeddings: ["google_fonts"],
  }),
  finding({
    family: "Ignored",
    family_group: "Ignored",
    license_verdict: "ok",
    privacy: "self_hosted",
  }),
];

describe("FindingsTable", () => {
  it("folds family variants into one expandable group row", () => {
    render(<FindingsTable findings={FINDINGS} />);
    expect(screen.getByText("Metropolis")).toBeInTheDocument();
    expect(screen.getByText(/2 variants/)).toBeInTheDocument();
    expect(screen.queryByText("metropolis-bold")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Metropolis/ }));
    expect(screen.getByText("metropolis-bold")).toBeInTheDocument();
  });

  it("defaults to 'Needs action': hides OK/self-hosted, keeps privacy-flagged OK", () => {
    render(<FindingsTable findings={FINDINGS} />);
    // Roboto is OK licence but third-party (GDPR) -> still shown.
    expect(screen.getByText("Roboto")).toBeInTheDocument();
    // Ignored is OK + self-hosted -> not actionable -> hidden.
    expect(screen.queryByText("Ignored")).not.toBeInTheDocument();
    // Switching to "All" reveals it.
    fireEvent.click(screen.getByRole("button", { name: /^All$/ }));
    expect(screen.getByText("Ignored")).toBeInTheDocument();
  });

  it("exposes sort state and a screen-reader label for flagged delivery", () => {
    render(<FindingsTable findings={FINDINGS} />);
    const header = screen.getByRole("columnheader", { name: /license/i });
    expect(header).toHaveAttribute("aria-sort");
    // Third-party delivery carries text, not colour/glyph alone.
    expect(screen.getByText(/privacy concern/i)).toBeInTheDocument();
  });
});
