import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { api } from "../lib/api";
import type { BackupInfo } from "../lib/api";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.click();
}

interface BackupListProps {
  backups: BackupInfo[];
  busy: boolean;
  onRestore: (name: string) => void;
}

// Saved workspace snapshots, newest first, each downloadable or restorable.
export function BackupList({ backups, busy, onRestore }: BackupListProps) {
  if (backups.length === 0) {
    return (
      <Card>
        <p className="text-sm text-muted">No snapshots yet. Save one above.</p>
      </Card>
    );
  }
  return (
    <ul className="space-y-2">
      {backups.map((b) => (
        <li key={b.name}>
          <Card className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{b.name}</p>
              <p className="text-sm text-muted">
                {new Date(b.created_at).toLocaleString()} · {formatSize(b.size_bytes)}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => download(api.backupDownloadUrl(b.name))}
              >
                Download
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => onRestore(b.name)}>
                Restore
              </Button>
            </div>
          </Card>
        </li>
      ))}
    </ul>
  );
}
