import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DiffResult, Finding, RunMeta, RunReport } from "../lib/api";
import { OverviewScreen } from "./OverviewScreen";

const api = vi.hoisted(() => ({
  getRun: vi.fn(),
  getRunDiff: vi.fn(),
  getFirstSeen: vi.fn(),
  exportCsvUrl: (id: string, source: string) => `/api/runs/${id}/export.csv?source=${source}`,
}));
vi.mock("../lib/api", () => ({ api }));

function finding(over: Partial<Finding> = {}): Finding {
  return {
    family: "Demo",
    family_group: "Demo",
    owner: "Acme",
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

function report(findings: Finding[]): RunReport {
  return {
    schema_version: 1,
    duration_seconds: 1,
    generated_at: "2026-06-30T12:00:00Z",
    summary: { total_findings: findings.length, needs_action: 0, by_verdict: {}, by_privacy: {} },
    findings,
    domains: [
      { domain: "example.com", is_live: true, pages_scanned: 3, live_hosts: [], subdomains: [], fonts: [] },
      { domain: "down.example", is_live: false, pages_scanned: 0, live_hosts: [], subdomains: [], fonts: [] },
    ],
  };
}

const meta = (id: string, needs: number): RunMeta => ({
  id,
  generated_at: "2026-06-30T12:00:00Z",
  summary: { total_findings: 0, needs_action: needs, by_verdict: {}, by_privacy: {} },
});

const CURRENT = report([
  finding({ family: "Bad", license_verdict: "violation" }),
  finding({ family: "Unsure", license_verdict: "needs_check", privacy: "third_party_api", embeddings: ["google_fonts"] }),
  finding({ family: "Fine" }),
]);
const PREVIOUS = report([finding({ family: "Fine" })]);
const DIFF: DiffResult = {
  new_findings: [finding({ family: "Bad" })],
  resolved_findings: [],
  changed: [],
  unchanged_count: 1,
};

function renderOverview(over: Partial<Parameters<typeof OverviewScreen>[0]> = {}) {
  const props = {
    runs: [meta("run-2.report.json", 2), meta("run-1.report.json", 0)],
    selectedId: "run-2.report.json",
    onSelect: vi.fn(),
    report: CURRENT,
    loading: false,
    view: "fonts" as const,
    onView: vi.fn(),
    source: "real" as const,
    onSource: vi.fn(),
    ...over,
  };
  render(<OverviewScreen {...props} />);
  return props;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getRun.mockResolvedValue(PREVIOUS);
  api.getRunDiff.mockResolvedValue(DIFF);
  api.getFirstSeen.mockResolvedValue([]);
});

describe("OverviewScreen", () => {
  it("shows Getting started when there are no real runs", () => {
    renderOverview({ runs: [], report: null });
    expect(screen.getByRole("heading", { name: "Getting started" })).toBeInTheDocument();
  });

  it("shows a demo hint when there are no demo runs", () => {
    renderOverview({ runs: [], report: null, source: "demo" });
    expect(screen.getByText(/No demo audits yet/)).toBeInTheDocument();
  });

  it("switches the data source", () => {
    const props = renderOverview();
    const group = screen.getByRole("group", { name: "Data source" });
    expect(within(group).getByRole("button", { name: "Your data" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(group).getByRole("button", { name: "Demo data" }));
    expect(props.onSource).toHaveBeenCalledWith("demo");
  });

  it("summarises the risk posture with deltas against the previous run", async () => {
    renderOverview();
    const posture = screen.getByRole("region", { name: "Risk posture" });
    expect(within(posture).getByText("Violation").previousSibling).toHaveTextContent("1");
    expect(within(posture).getByText("Need check").previousSibling).toHaveTextContent("1");
    expect(within(posture).getByText("Privacy").previousSibling).toHaveTextContent("1");
    // Previous run had 0 violations → ↑1; OK unchanged → ±0.
    await waitFor(() => expect(within(posture).getAllByText("↑1 vs last")).toHaveLength(2));
    expect(within(posture).getByText("±0 vs last")).toBeInTheDocument();
    expect(api.getRun).toHaveBeenCalledWith("run-1.report.json", "real");
  });

  it("flags third-party delivery and shows the portfolio", () => {
    renderOverview();
    expect(screen.getByText(/Privacy \(GDPR\/RODO\)/)).toBeInTheDocument();
    expect(screen.getByText("Unreachable").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("Live").previousSibling).toHaveTextContent("1");
  });

  it("lists changes since the last run", async () => {
    renderOverview();
    expect(await screen.findByText("New (1)")).toBeInTheDocument();
    expect(api.getRunDiff).toHaveBeenCalledWith("run-2.report.json", "real");
  });

  it("has no comparison for the oldest run", () => {
    renderOverview({ selectedId: "run-1.report.json" });
    expect(api.getRun).not.toHaveBeenCalled();
    expect(api.getRunDiff).not.toHaveBeenCalled();
  });

  it("selects a run and links its CSV export", () => {
    const props = renderOverview();
    fireEvent.change(screen.getByLabelText("Run"), { target: { value: "run-1.report.json" } });
    expect(props.onSelect).toHaveBeenCalledWith("run-1.report.json");
    expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
      "href",
      "/api/runs/run-2.report.json/export.csv?source=real",
    );
  });
});
