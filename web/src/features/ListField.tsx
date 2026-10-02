const toLines = (xs: string[]) => xs.join("\n");
const fromLines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

interface ListFieldProps {
  label: string;
  hint: string;
  value: string[];
  onChange: (value: string[]) => void;
}

// A string list edited as text, one item per line.
export function ListField({ label, hint, value, onChange }: ListFieldProps) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <textarea
        value={toLines(value)}
        onChange={(e) => onChange(fromLines(e.target.value))}
        rows={4}
        className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-xs text-ink"
      />
      <span className="mt-1 block text-xs text-faint">{hint} · one per line</span>
    </label>
  );
}
