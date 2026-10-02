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

  it("filters by search text (family or owner) and by license verdict", () => {
    render(<FindingsTable findings={FINDINGS} />);
    fireEvent.click(screen.getByRole("button", { name: /^All$/ }));
    fireEvent.change(screen.getByLabelText("Search findings"), { target: { value: "robo" } });
    expect(screen.getByText("Roboto")).toBeInTheDocument();
    expect(screen.queryByText("Metropolis")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search findings"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("License"), { target: { value: "ok" } });
    expect(screen.getByText("Ignored")).toBeInTheDocument();
    expect(screen.queryByText("Metropolis")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("License"), { target: { value: "violation" } });
    fireEvent.change(screen.getByLabelText("Search findings"), { target: { value: "zzz" } });
    expect(screen.getByText("No findings match the filters.")).toBeInTheDocument();
  });

  it("can list variants individually instead of grouped", () => {
    render(<FindingsTable findings={FINDINGS} />);
    fireEvent.click(screen.getByLabelText("Group variants"));
    expect(screen.getByText("metropolis")).toBeInTheDocument();
    expect(screen.getByText("metropolis-bold")).toBeInTheDocument();
    expect(screen.queryByText(/\d+ variants/)).not.toBeInTheDocument();
  });

  it("counts hidden no-action fonts and sorts by severity", () => {
    render(<FindingsTable findings={FINDINGS} />);
    expect(screen.getByText(/1 OK \/ no-action font hidden/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Group variants"));
    const families = () =>
      screen.getAllByRole("button", { expanded: false }).map((b) => b.textContent?.slice(2));
    expect(families()).toEqual(["metropolis", "metropolis-bold", "Roboto"]);
    fireEvent.click(screen.getByRole("button", { name: /Sort by severity/ }));
    expect(families()).toEqual(["Roboto", "metropolis-bold", "metropolis"]);
  });

  it("expands a finding into its explanation", () => {
    render(<FindingsTable findings={FINDINGS} />);
    const row = screen.getByRole("button", { name: /Roboto/ });
    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById(row.getAttribute("aria-controls")!)).toBeInTheDocument();
  });

  it("exposes sort state and a screen-reader label for flagged delivery", () => {
    render(<FindingsTable findings={FINDINGS} />);
    const header = screen.getByRole("columnheader", { name: /license/i });
    expect(header).toHaveAttribute("aria-sort");
    // Third-party delivery carries text, not colour/glyph alone.
    expect(screen.getByText(/privacy concern/i)).toBeInTheDocument();
  });
});
