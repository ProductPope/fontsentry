import { useRef } from "react";
import { Button } from "../components/Button";

interface TargetsEditorProps {
  text: string;
  onText: (text: string) => void;
  saving: boolean;
  onSave: () => void;
  onImportCsv: (file: File) => void;
}

// The domain list as one-per-line text, with save and CSV import.
export function TargetsEditor({ text, onText, saving, onSave, onImportCsv }: TargetsEditorProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2">
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        rows={8}
        spellCheck={false}
        aria-label="Domains to scan, one per line"
        placeholder={"example.com\nexample.org"}
        className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-sm text-ink"
      />
      <div className="flex gap-2">
        <Button onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save domains"}
        </Button>
        <Button variant="secondary" onClick={() => fileRef.current?.click()}>
          Import CSV
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImportCsv(file);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
