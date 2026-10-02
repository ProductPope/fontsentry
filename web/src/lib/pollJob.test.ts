import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Job } from "./api";
import { pollJob } from "./pollJob";

const api = vi.hoisted(() => ({ getJob: vi.fn() }));
vi.mock("./api", () => ({ api }));

const job = (over: Partial<Job>): Job => ({
  id: "j",
  status: "running",
  mode: "real",
  run_id: null,
  error: null,
  phase: "",
  message: "",
  current: 0,
  total: 0,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("pollJob", () => {
  it("reports progress until the job is done, then returns its run id", async () => {
    api.getJob
      .mockResolvedValueOnce(job({ current: 1 }))
      .mockResolvedValueOnce(job({ status: "done", run_id: "run.json" }));
    const progress = vi.fn();
    const result = pollJob("j", progress);
    await vi.runAllTimersAsync();
    await expect(result).resolves.toBe("run.json");
    expect(progress).toHaveBeenCalledTimes(2);
  });

  it("fails with the job's own error", async () => {
    api.getJob.mockResolvedValue(job({ status: "error", error: "no config found" }));
    await expect(pollJob("j", vi.fn())).rejects.toThrow("no config found");
  });

  it("tolerates transient errors but gives up after five in a row", async () => {
    api.getJob
      .mockRejectedValueOnce(new Error("blip"))
      .mockResolvedValueOnce(job({ status: "done", run_id: "run.json" }));
    const recovered = pollJob("j", vi.fn());
    await vi.runAllTimersAsync();
    await expect(recovered).resolves.toBe("run.json");

    api.getJob.mockReset().mockRejectedValue(new Error("server gone"));
    const lost = pollJob("j", vi.fn());
    const assertion = expect(lost).rejects.toThrow("server gone");
    await vi.runAllTimersAsync();
    await assertion;
    expect(api.getJob).toHaveBeenCalledTimes(5);
  });
});
