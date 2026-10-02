import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RunMeta } from "../lib/api";
import { AuditsScreen } from "./AuditsScreen";

const api = vi.hoisted(() => ({ getSchedules: vi.fn(), deleteSchedule: vi.fn() }));
vi.mock("../lib/api", () => ({ api }));

const run = (id: string): RunMeta => ({
  id,
  generated_at: "2026-06-30T12:00:00Z",
  summary: {
    total_findings: 5,
    needs_action: 2,
    by_verdict: { violation: 1, needs_check: 1, ok: 3 },
    by_privacy: {},
  },
});

function renderAudits(runs: RunMeta[] = [run("run-2.report.json"), run("run-1.report.json")]) {
  const onOpenRun = vi.fn();
  const notify = vi.fn();
  render(
    <AuditsScreen runs={runs} selectedId="run-1.report.json" onOpenRun={onOpenRun} notify={notify} />,
  );
  return { onOpenRun, notify };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getSchedules.mockResolvedValue([
    { name: "weekly-audit", next_run: "6/8/2026 6:00:00 AM", status: "Ready" },
  ]);
  api.deleteSchedule.mockResolvedValue({ deleted: "weekly-audit" });
});

describe("AuditsScreen", () => {
  it("lists past audits with their verdict counts and opens one", () => {
    const { onOpenRun } = renderAudits();
    const newest = screen.getByRole("button", { name: /run-2\.report\.json/ });
    expect(newest).toHaveTextContent("1 violation");
    expect(newest).toHaveTextContent("2/5 need action");
    expect(screen.getByRole("button", { name: /run-1\.report\.json/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    fireEvent.click(newest);
    expect(onOpenRun).toHaveBeenCalledWith("run-2.report.json");
  });

  it("shows empty states", async () => {
    api.getSchedules.mockResolvedValue([]);
    renderAudits([]);
    expect(screen.getByText(/No audits yet/)).toBeInTheDocument();
    expect(await screen.findByText("No recurring audits scheduled.")).toBeInTheDocument();
  });

  it("lists and deletes schedules", async () => {
    const { notify } = renderAudits();
    expect(await screen.findByText("weekly-audit")).toBeInTheDocument();
    expect(screen.getByText("next 6/8/2026 6:00:00 AM")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete weekly-audit" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("Schedule removed", "success"));
    expect(api.deleteSchedule).toHaveBeenCalledWith("weekly-audit");
    expect(api.getSchedules).toHaveBeenCalledTimes(2);
  });

  it("opens the schedule dialog", async () => {
    renderAudits();
    fireEvent.click(screen.getByRole("button", { name: "New schedule" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
