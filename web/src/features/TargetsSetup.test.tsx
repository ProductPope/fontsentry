import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Target } from "../lib/api";
import { TargetsSetup } from "./TargetsSetup";

const api = vi.hoisted(() => ({
  getTargets: vi.fn(),
  saveTargets: vi.fn(),
  getRuns: vi.fn(),
  getRun: vi.fn(),
}));
vi.mock("../lib/api", () => ({ api }));

const TARGETS: Target[] = [
  { domain: "example.com", subdomain_seeds: ["shop"] },
  { domain: "down.example", subdomain_seeds: [] },
];

function renderTargets() {
  const notify = vi.fn();
  const onRunAudit = vi.fn();
  render(<TargetsSetup notify={notify} onRunAudit={onRunAudit} running={false} />);
  return { notify, onRunAudit };
}

const textarea = () => screen.getByLabelText("Domains to scan, one per line");

beforeEach(() => {
  vi.clearAllMocks();
  api.getTargets.mockResolvedValue({ targets: TARGETS });
  api.saveTargets.mockImplementation(async (t: { targets: Target[] }) => t);
  api.getRuns.mockResolvedValue([{ id: "run-1.report.json" }]);
  api.getRun.mockResolvedValue({
    domains: [
      { domain: "example.com", is_live: true },
      { domain: "down.example", is_live: false },
    ],
  });
});

describe("TargetsSetup", () => {
  it("loads the targets and their reachability in the latest run", async () => {
    renderTargets();
    await waitFor(() => expect(textarea()).toHaveValue("example.com\ndown.example"));
    fireEvent.change(textarea(), { target: { value: "example.com\ndown.example\nnew.example" } });
    const table = screen.getByRole("table", { name: /reachability/ });
    await waitFor(() => expect(within(table).getByText("live")).toBeInTheDocument());
    expect(within(table).getByText("unreachable")).toBeInTheDocument();
    expect(within(table).getByText("not scanned")).toBeInTheDocument();
  });

  it("saves edits, keeping each domain's subdomain seeds, then offers an audit", async () => {
    const { onRunAudit } = renderTargets();
    await waitFor(() => expect(textarea()).toHaveValue("example.com\ndown.example"));
    fireEvent.change(textarea(), { target: { value: "https://Example.com/\nfresh.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Save domains" }));

    expect(await screen.findByRole("heading", { name: "Domains saved" })).toBeInTheDocument();
    expect(api.saveTargets).toHaveBeenCalledWith({
      targets: [
        { domain: "https://Example.com/", subdomain_seeds: ["shop"] },
        { domain: "fresh.example", subdomain_seeds: [] },
      ],
    });
    fireEvent.click(screen.getByRole("button", { name: "Run audit" }));
    expect(onRunAudit).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Edit domains" }));
    expect(textarea()).toBeInTheDocument();
  });

  it("says so when a save changed nothing", async () => {
    const { notify } = renderTargets();
    await waitFor(() => expect(textarea()).toHaveValue("example.com\ndown.example"));
    fireEvent.click(screen.getByRole("button", { name: "Save domains" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("No changes to save", "info"));
    expect(screen.queryByRole("heading", { name: "Domains saved" })).not.toBeInTheDocument();
  });

  it("imports new domains from a CSV's first column", async () => {
    const { notify } = renderTargets();
    await waitFor(() => expect(textarea()).toHaveValue("example.com\ndown.example"));
    const csv = "domain,owner\nhttps://example.com/,x\nnew.example,y\n";
    const input = document.querySelector('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File([csv], "t.csv")] } });
    await waitFor(() =>
      expect(textarea()).toHaveValue("example.com\ndown.example\nnew.example"),
    );
    expect(notify).toHaveBeenCalledWith("Imported 1 new domain(s) — review, then Save", "info");
  });

  it("rejects a CSV without domains", async () => {
    const { notify } = renderTargets();
    await waitFor(() => expect(textarea()).toHaveValue("example.com\ndown.example"));
    const input = document.querySelector('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(["domain\n"], "t.csv")] } });
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith("No domains found in that CSV", "error"),
    );
  });
});
