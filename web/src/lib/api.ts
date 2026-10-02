// Typed client for the FontSentry backend.
//
// The types are generated from the server's OpenAPI schema (api-schema.d.ts,
// via `npm run gen:api`), never written by hand, so the UI cannot drift from the
// pydantic models. Regenerate after any backend model change; CI fails otherwise.

import type { components } from "./api-schema";

type Schemas = components["schemas"];

// The schema marks every field with a default as optional (it doubles as the
// request shape), but responses always carry every field. `Served` removes
// the `?` — nullability (`| null`) is kept exactly as the server declares it.
type Served<T> = T extends (infer U)[]
  ? Served<U>[]
  : T extends object
    ? { [K in keyof T]-?: Served<Exclude<T[K], undefined>> }
    : T;

export type LicenseVerdict = Schemas["LicenseVerdict"];
export type PrivacyClass = Schemas["PrivacyClass"];

export type FontMetadata = Served<Schemas["FontMetadata"]>;
export type Finding = Served<Schemas["Finding"]>;
export type RunSummary = Served<Schemas["RunSummary"]>;
export type HostAsset = Served<Schemas["HostAsset"]>;
export type DomainFont = Served<Schemas["DomainFont"]>;
export type DomainReport = Served<Schemas["DomainReport"]>;
export type RunReport = Served<Schemas["RunReport"]>;
export type FindingDelta = Served<Schemas["FindingDelta"]>;
export type DiffResult = Served<Schemas["DiffResult"]>;
export type RunMeta = Served<Schemas["RunMeta"]>;
export type FirstSeen = Served<Schemas["FirstSeen"]>;
export type KnownFont = Served<Schemas["KnownFont"]>;
export type ScanEstimate = Served<Schemas["ScanEstimate"]>;
export type ScheduleInfo = Served<Schemas["ScheduleInfo"]>;
export type ScheduleSpec = Served<Schemas["ScheduleSpec"]>;
export type Job = Served<Schemas["Job"]>;
export type Target = Served<Schemas["Target"]>;
export type TargetsConfig = Served<Schemas["TargetsConfig"]>;
export type RegistryEntry = Served<Schemas["RegistryEntry"]>;
export type RegistryConfig = Served<Schemas["Registry"]>;
export type RegistryImportResult = Served<Schemas["RegistryImportResult"]>;
export type BackupInfo = Served<Schemas["BackupInfo"]>;
export type FamilySpec = Served<Schemas["FamilySpec"]>;
export type SelfHostProhibited = Served<Schemas["SelfHostProhibited"]>;
export type RulesConfig = Served<Schemas["RulesConfig"]>;

// The server's own explanation (FastAPI's `detail`) when there is one, so the
// UI can show "an audit is already running" rather than "Conflict".
async function errorFrom(res: Response): Promise<Error> {
  let detail = res.statusText;
  try {
    const body = (await res.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // non-JSON error body; keep statusText
  }
  return new Error(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}

export const api = {
  getRuns: (source: "real" | "demo" = "real") => request<RunMeta[]>(`/api/runs?source=${source}`),
  getFirstSeen: (source: "real" | "demo" = "real") =>
    request<FirstSeen[]>(`/api/first-seen?source=${source}`),
  getKnownFonts: () => request<KnownFont[]>("/api/known-fonts"),
  getRun: (id: string, source: "real" | "demo" = "real") =>
    request<RunReport>(`/api/runs/${encodeURIComponent(id)}?source=${source}`),
  getRunDiff: (id: string, source: "real" | "demo" = "real") =>
    request<DiffResult>(`/api/runs/${encodeURIComponent(id)}/diff?source=${source}`),
  exportCsvUrl: (id: string, source: "real" | "demo" = "real") =>
    `/api/runs/${encodeURIComponent(id)}/export.csv?source=${source}`,
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
  getActiveJobs: () => request<Job[]>("/api/jobs"),
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
  importRegistry: (registry: RegistryConfig) =>
    request<RegistryImportResult>("/api/config/registry/import", {
      method: "POST",
      body: JSON.stringify(registry),
    }),
  registryCsvUrl: "/api/config/registry/export.csv",
  importRegistryCsv: (csv: string) =>
    request<RegistryImportResult>("/api/config/registry/import.csv", {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: csv,
    }),
  listBackups: () => request<BackupInfo[]>("/api/workspace/backups"),
  snapshotWorkspace: () => request<BackupInfo>("/api/workspace/snapshot", { method: "POST" }),
  workspaceExportUrl: "/api/workspace/export",
  backupDownloadUrl: (name: string) => `/api/workspace/backups/${encodeURIComponent(name)}`,
  restoreBackup: (name: string) =>
    request<{ restored: string }>(`/api/workspace/restore/${encodeURIComponent(name)}`, {
      method: "POST",
    }),
  importWorkspace: (file: File) =>
    request<{ restored: string }>("/api/workspace/import", {
      method: "POST",
      headers: { "Content-Type": "application/zip" },
      body: file,
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
    if (!res.ok) throw await errorFrom(res);
    return (await res.json()) as { name: string };
  },
  proofUrl: (name: string) => `/api/registry/proof/${encodeURIComponent(name)}`,
};
