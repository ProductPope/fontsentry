// Typed client for the FontSentry backend. Mirrors the pydantic models.

export type Band = "low" | "medium" | "high";
export type Status = "open" | "resolved";

export interface FontMetadata {
  family_name: string | null;
  foundry: string | null;
  designer: string | null;
  copyright: string | null;
  license_description: string | null;
  license_url: string | null;
  unique_id: string | null;
  num_glyphs: number | null;
}

export interface TriggeredRule {
  id: string;
  description: string;
  weight: number;
  confidence: number;
  points: number;
}

export interface Finding {
  family: string;
  foundry: string | null;
  domains: string[];
  formats: string[];
  embeddings: string[];
  metadata: FontMetadata | null;
  score: number;
  band: Band;
  status: Status;
  triggered_rules: TriggeredRule[];
  registry_match: boolean;
  suppression_reason: string | null;
}

export interface RunSummary {
  total_findings: number;
  open_findings: number;
  resolved_findings: number;
  by_band: Partial<Record<Band, number>>;
}

export interface DomainFont {
  family: string;
  foundry: string | null;
  band: Band;
  status: Status;
  embeddings: string[];
  formats: string[];
  hosts: string[];
}

export interface DomainReport {
  domain: string;
  is_live: boolean;
  pages_scanned: number;
  live_hosts: string[];
  subdomains: string[];
  fonts: DomainFont[];
}

export interface RunReport {
  schema_version: number;
  generated_at: string;
  summary: RunSummary;
  findings: Finding[];
  domains: DomainReport[];
}

export interface RunMeta {
  id: string;
  generated_at: string;
  summary: RunSummary;
}

export interface FindingDelta {
  family: string;
  foundry: string | null;
  old_score: number;
  new_score: number;
  old_domains: string[];
  new_domains: string[];
}

export interface DiffResult {
  new_findings: Finding[];
  resolved_findings: Finding[];
  changed: FindingDelta[];
  unchanged_count: number;
}

export interface ScheduleInfo {
  name: string;
  next_run: string | null;
  status: string | null;
}

export interface ScheduleSpec {
  name: string;
  frequency: "daily" | "weekly";
  time: string;
  day_of_week: "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";
  mode: "demo" | "real";
}

export interface Job {
  id: string;
  status: "running" | "done" | "error";
  run_id: string | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  getRuns: () => request<RunMeta[]>("/api/runs"),
  getRun: (id: string) => request<RunReport>(`/api/runs/${encodeURIComponent(id)}`),
  getDiff: (previous: string, current: string) =>
    request<DiffResult>(
      `/api/diff?previous=${encodeURIComponent(previous)}&current=${encodeURIComponent(current)}`,
    ),
  startScan: (mode: "demo" | "real") =>
    request<{ job_id: string }>("/api/scan", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  getJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  getSchedules: () => request<ScheduleInfo[]>("/api/schedules"),
  createSchedule: (spec: ScheduleSpec) =>
    request<ScheduleInfo>("/api/schedules", {
      method: "POST",
      body: JSON.stringify(spec),
    }),
  deleteSchedule: (name: string) =>
    request<{ deleted: string }>(`/api/schedules/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
};
