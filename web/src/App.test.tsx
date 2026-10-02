import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { Job, RunMeta, RunReport } from "./lib/api";

const api = vi.hoisted(() => ({
  getRuns: vi.fn(),
  getRun: vi.fn(),
  getRunDiff: vi.fn(),
  getActiveJobs: vi.fn(),
  getJob: vi.fn(),
  startScan: vi.fn(),
  getTargets: vi.fn(),
  scanEstimate: vi.fn(),
  exportCsvUrl: () => "/export.csv",
}));
vi.mock("./lib/api", () => ({ api }));

const meta = (id: string): RunMeta => ({
  id,
  generated_at: "2026-06-30T12:00:00Z",
  summary: { total_findings: 0, needs_action: 0, by_verdict: {}, by_privacy: {} },
});

const REPORT: RunReport = {
  schema_version: 1,
  duration_seconds: 1,
  generated_at: "2026-06-30T12:00:00Z",
  summary: { total_findings: 0, needs_action: 0, by_verdict: {}, by_privacy: {} },
  findings: [],
  domains: [],
};

const job = (over: Partial<Job> = {}): Job => ({
  id: "job-1",
  status: "running",
  mode: "demo",
  run_id: null,
  error: null,
  phase: "detect",
  message: "",
  current: 1,
  total: 2,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  window.location.hash = "";
  api.getRuns.mockResolvedValue([meta("run-2.report.json"), meta("run-1.report.json")]);
  api.getRun.mockResolvedValue(REPORT);
  api.getRunDiff.mockResolvedValue({
    new_findings: [],
    resolved_findings: [],
    changed: [],
    unchanged_count: 0,
  });
  api.getActiveJobs.mockResolvedValue([]);
  api.getTargets.mockResolvedValue({ targets: [] });
  api.scanEstimate.mockResolvedValue({ eta_seconds: null, based_on_runs: 0 });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("App", () => {
  it("loads the newest run of the user's data on the Overview", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Run")).toHaveValue("run-2.report.json"));
    expect(api.getRuns).toHaveBeenCalledWith("real");
    expect(api.getRun).toHaveBeenCalledWith("run-2.report.json", "real");
  });

  it("runs an audit from the header and opens its result", async () => {
    api.startScan.mockResolvedValue({ job_id: "job-1" });
    api.getJob.mockResolvedValue(job({ status: "done", run_id: "run-3.report.json" }));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Start audit" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Demo data" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Start audit" }));

    expect(await screen.findByText("Audit complete")).toBeInTheDocument();
    expect(api.startScan).toHaveBeenCalledWith("demo", false, 25);
    // The finished run is opened in its own data set.
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith("run-3.report.json", "demo"));
  });

  it("shows a failed audit's error until dismissed", async () => {
    api.startScan.mockRejectedValue(new Error("an audit is already running"));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Start audit" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start audit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("an audit is already running");
  });

  it("re-attaches to a scan already running on the server", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.getActiveJobs.mockResolvedValue([job()]);
    api.getJob
      .mockResolvedValueOnce(job({ current: 2 }))
      .mockResolvedValue(job({ status: "done", run_id: "run-3.report.json" }));
    render(<App />);
    expect(await screen.findByText(/Reattached to a running audit/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Auditing…" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(await screen.findByText("Audit complete")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start audit" })).toBeEnabled();
  });

  it("navigates between sections from the sidebar", async () => {
    render(<App />);
    fireEvent.click(screen.getAllByRole("button", { name: "How it works" })[0]!);
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1, name: "How it works" })).toBeInTheDocument(),
    );
  });
});
