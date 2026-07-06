import type { RegistryImportResult } from "./api";

/** One-line human summary of a registry import. Replacements are always named:
 * an import can overwrite an entry with a less strict one (e.g. no expiry),
 * and that must be visible to the operator, not folded into a total. */
export function importSummary(res: RegistryImportResult): string {
  return `Imported — ${res.added} added, ${res.replaced} replaced; ${res.registry.entries.length} licenses total`;
}
