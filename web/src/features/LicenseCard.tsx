import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { api } from "../lib/api";
import type { RegistryEntry } from "../lib/api";
import { cn } from "../lib/cn";
import { expiryBadge } from "../lib/registryForm";

interface LicenseCardProps {
  entry: RegistryEntry;
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
}

// One owned license in the registry grid: identity, expiry badge, scope, proof.
export function LicenseCard({ entry: e, busy, onEdit, onDelete }: LicenseCardProps) {
  const badge = expiryBadge(e.valid_until);
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-semibold">{e.family || "—"}</div>
          <div className="truncate text-sm text-muted">{e.owner || "—"}</div>
        </div>
        <span className={cn("shrink-0 text-xs font-medium", badge.tone)}>{badge.label}</span>
      </div>
      {e.license_type && <div className="text-sm text-muted">{e.license_type}</div>}
      <dl className="space-y-1 text-sm">
        <Line label="Domains">
          <span className="font-mono text-xs">
            {e.allowed_domains.includes("*") ? "any domain" : e.allowed_domains.join(", ") || "—"}
          </span>
        </Line>
        {e.max_domains != null && (
          <Line label="Max">
            <span className="font-mono">{e.max_domains}</span>
          </Line>
        )}
        {e.proof_path && (
          <Line label="Proof">
            <a
              href={api.proofUrl(e.proof_path)}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline"
            >
              {e.proof_path}
            </a>
          </Line>
        )}
        {e.notes && <Line label="Notes">{e.notes}</Line>}
      </dl>
      <div className="mt-auto flex gap-2 pt-1">
        <Button variant="secondary" onClick={onEdit} disabled={busy}>
          Edit
        </Button>
        <Button variant="ghost" onClick={onDelete} disabled={busy}>
          Delete
        </Button>
      </div>
    </Card>
  );
}

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-20 shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}
