import { useRef } from "react";
import { Button } from "../components/Button";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";
import type { RegistryConfig, RegistryEntry } from "../lib/api";
import { importSummary } from "../lib/importSummary";

interface RegistryTransferProps {
  entries: RegistryEntry[];
  busy: boolean;
  setBusy: (busy: boolean) => void;
  onImported: (entries: RegistryEntry[]) => void;
  notify: (message: string, kind: ToastKind) => void;
}

function download(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
}

// Export/import the registry as JSON or CSV. Imports merge by owner+family on
// the server (never delete), so re-importing a backup onto a machine with
// existing licenses is safe. Proofs are files, not rows — they are not carried
// in the JSON/CSV and stay under registry/proofs/.
export function RegistryTransfer({
  entries,
  busy,
  setBusy,
  onImported,
  notify,
}: RegistryTransferProps) {
  const jsonRef = useRef<HTMLInputElement>(null);
  const csvRef = useRef<HTMLInputElement>(null);

  function exportJson() {
    const blob = new Blob([JSON.stringify({ entries }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    download(url, "fontsentry-registry.json");
    URL.revokeObjectURL(url);
  }

  async function runImport(fallbackError: string, call: () => Promise<void>) {
    setBusy(true);
    try {
      await call();
    } catch (e) {
      notify(e instanceof Error ? e.message : fallbackError, "error");
    } finally {
      setBusy(false);
    }
  }

  const importJson = (file: File) =>
    runImport("Import failed — expected a registry JSON", async () => {
      const parsed = JSON.parse(await file.text()) as RegistryConfig;
      const res = await api.importRegistry(parsed);
      onImported(res.registry.entries);
      // Replacements are called out: an import can overwrite an entry with a
      // less strict one, and that must not happen invisibly.
      notify(importSummary(res), res.replaced > 0 ? "info" : "success");
    });

  // CSV columns: owner, family, license_type, allowed_domains (pipe-separated),
  // max_domains, proof_path, invoice_path, valid_until (ISO date), notes. Bad rows
  // are skipped and reported; good rows are still merged in.
  const importCsv = (file: File) =>
    runImport("CSV import failed", async () => {
      const res = await api.importRegistryCsv(await file.text());
      onImported(res.registry.entries);
      if (res.errors.length > 0) {
        notify(
          `${importSummary(res)}; ${res.errors.length} skipped row(s): ${res.errors[0]}`,
          "info",
        );
      } else {
        notify(importSummary(res), res.replaced > 0 ? "info" : "success");
      }
    });

  const empty = entries.length === 0;
  return (
    <>
      <Button variant="secondary" disabled={busy || empty} onClick={exportJson}>
        Export JSON
      </Button>
      <Button variant="secondary" disabled={busy} onClick={() => jsonRef.current?.click()}>
        Import JSON
      </Button>
      <input
        ref={jsonRef}
        type="file"
        accept="application/json,.json"
        aria-label="Import registry JSON file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // allow re-selecting the same file
          if (file) void importJson(file);
        }}
      />
      <Button
        variant="secondary"
        disabled={busy || empty}
        onClick={() => download(api.registryCsvUrl, "fontsentry-registry.csv")}
      >
        Export CSV
      </Button>
      <Button variant="secondary" disabled={busy} onClick={() => csvRef.current?.click()}>
        Import CSV
      </Button>
      <input
        ref={csvRef}
        type="file"
        accept="text/csv,.csv"
        aria-label="Import registry CSV file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void importCsv(file);
        }}
      />
    </>
  );
}
