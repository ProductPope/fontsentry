import { api } from "./api";
import type { Job } from "./api";

const POLL_INTERVAL_MS = 1500;
const RETRY_DELAY_MS = 2000;
const MAX_CONSECUTIVE_ERRORS = 5;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Poll until the backend job finishes and return its run id. A real
// multi-domain crawl is politeness-bound and can run for many minutes, so there
// is no fixed attempt cap — we follow the job's own status and only give up if
// it errors or the job can't be reached several times in a row (transient blips
// during a busy crawl are tolerated).
export async function pollJob(jobId: string, onProgress: (job: Job) => void): Promise<string> {
  let consecutiveErrors = 0;
  for (;;) {
    let job: Job;
    try {
      job = await api.getJob(jobId);
      consecutiveErrors = 0;
    } catch (e) {
      if (++consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        throw e instanceof Error ? e : new Error("lost contact with the scan");
      }
      await sleep(RETRY_DELAY_MS);
      continue;
    }
    onProgress(job);
    if (job.status === "done" && job.run_id) return job.run_id;
    if (job.status === "error") throw new Error(job.error ?? "scan failed");
    await sleep(POLL_INTERVAL_MS);
  }
}
