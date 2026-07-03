// Typed client for the FontSentry backend. Mirrors the pydantic models.

export type Band = "low" | "medium" | "high";
export type Status = "open" | "resolved";

export interface FontMetadata {
  family_name: string | null;
  owner: string | null;
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
  owner: string | null;
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
  example_urls: string[];
  page_count: number;
  applied: boolean;
}

export interface RunSummary {
  total_findings: number;
  open_findings: number;
  resolved_findings: number;
  by_band: Partial<Record<Band, number>>;
}

export interface HostAsset {
  host: string;
  urls: string[];
}

export interface DomainFont {
  family: string;
  owner: string | null;
  band: Band;
  status: Status;
  embeddings: string[];
  formats: string[];
  hosts: string[];
  assets: HostAsset[];
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

export interface FindingDelta {
  family: string;
  owner: string | null;
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

export interface RunMeta {
  id: string;
  generated_at: string;
  summary: RunSummary;
}

export interface FirstSeen {
  domain: string;
  family: string;
  first_seen: string; // ISO datetime
}

export interface ScanEstimate {
  eta_seconds: number | null;
  based_on_runs: number;
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
  phase: string; // "" | "discover" | "detect" | "score" | "report"
  message: string;
  current: number;
  total: number; // 0 = indeterminate
}

export interface Target {
  domain: string;
  subdomain_seeds: string[];
}

export interface TargetsConfig {
  targets: Target[];
}

export interface RegistryEntry {
  owner: string;
  family: string;
  license_type: string;
  allowed_domains: string[];
  max_domains: number | null;
  proof_path: string | null;
  invoice_path: string | null;
  valid_until: string | null; // ISO date (YYYY-MM-DD)
  notes: string | null;
}

export interface RegistryConfig {
  entries: RegistryEntry[];
}

export interface RuleCondition {
  type: string;
  params: Record<string, unknown>;
}

export interface Rule {
  id: string;
  description: string;
  weight: number;
  confidence: number;
  when: RuleCondition;
}

export interface BandThresholds {
  medium: number;
  high: number;
}

export interface Scoring {
  max_raw: number;
  bands: BandThresholds;
}

export interface RulesConfig {
  scoring: Scoring;
  rules: Rule[];
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
  getFirstSeen: () => request<FirstSeen[]>("/api/first-seen"),
  getRun: (id: string) => request<RunReport>(`/api/runs/${encodeURIComponent(id)}`),
  getRunDiff: (id: string) => request<DiffResult>(`/api/runs/${encodeURIComponent(id)}/diff`),
  exportCsvUrl: (id: string) => `/api/runs/${encodeURIComponent(id)}/export.csv`,
  startScan: (mode: "demo" | "real", discoverSubdomains = false, maxPages?: number) =>
    request<{ job_id: string }>("/api/scan", {
      method: "POST",
      body: JSON.stringify({
        mode,
        discover_subdomains: discoverSubdomains,
        max_pages_per_domain: maxPages,
      }),
    }),
  scanEstimate: (hosts: number, maxPages: number) =>
    request<ScanEstimate>(`/api/scan/estimate?hosts=${hosts}&max_pages=${maxPages}`),
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
  getTargets: () => request<TargetsConfig>("/api/config/targets"),
  saveTargets: (targets: TargetsConfig) =>
    request<TargetsConfig>("/api/config/targets", {
      method: "PUT",
      body: JSON.stringify(targets),
    }),
  getRegistry: () => request<RegistryConfig>("/api/config/registry"),
  saveRegistry: (registry: RegistryConfig) =>
    request<RegistryConfig>("/api/config/registry", {
      method: "PUT",
      body: JSON.stringify(registry),
    }),
  getRules: () => request<RulesConfig>("/api/config/rules"),
  saveRules: (rules: RulesConfig) =>
    request<RulesConfig>("/api/config/rules", {
      method: "PUT",
      body: JSON.stringify(rules),
    }),
  // Multipart upload — no JSON Content-Type (the browser sets the boundary).
  uploadProof: async (file: File): Promise<{ name: string }> => {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/registry/proof", { method: "POST", body });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const b = (await res.json()) as { detail?: string };
        if (b.detail) detail = b.detail;
      } catch {
        // non-JSON error body; keep statusText
      }
      throw new Error(detail);
    }
    return (await res.json()) as { name: string };
  },
  proofUrl: (name: string) => `/api/registry/proof/${encodeURIComponent(name)}`,
};
