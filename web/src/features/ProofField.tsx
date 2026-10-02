import { useRef, useState } from "react";
import { Button } from "../components/Button";
import { Field } from "../components/Field";
import type { ToastKind } from "../components/Toast";
import { api } from "../lib/api";

interface ProofFieldProps {
  value: string | null;
  onChange: (proofPath: string | null) => void;
  notify: (message: string, kind: ToastKind) => void;
}

// License proof: upload a file, or show/remove the attached one. The stored name
// comes from the server (it may differ from the upload's, e.g. "invoice-1.pdf").
export function ProofField({ value, onChange, notify }: ProofFieldProps) {
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function upload(file: File) {
    setUploading(true);
    try {
      const { name } = await api.uploadProof(file);
      onChange(name);
      notify("Proof attached", "success");
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not upload proof", "error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Field label="Proof (PDF or image, optional)">
      {value ? (
        <div className="flex items-center gap-2 text-sm">
          <a
            href={api.proofUrl(value)}
            target="_blank"
            rel="noreferrer"
            className="min-w-0 truncate text-accent underline"
          >
            {value}
          </a>
          <Button variant="ghost" className="px-2" onClick={() => onChange(null)}>
            Remove
          </Button>
        </div>
      ) : (
        <>
          <Button
            variant="secondary"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? "Uploading…" : "Attach file"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
              e.target.value = "";
            }}
          />
        </>
      )}
    </Field>
  );
}
