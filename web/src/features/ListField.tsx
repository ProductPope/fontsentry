import { useState } from "react";

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

// A string list edited as text, one item per line. The raw text is kept while
// typing: re-rendering from the parsed list would drop the empty line a fresh
// Enter creates, so a new item could never be typed (only pasted).
export function ListField({ label, hint, value, onChange }: ListFieldProps) {
  const [text, setText] = useState(() => toLines(value));
  // Adopt a value from outside (load, save) only when it means something else
  // than the text being edited.
  if (toLines(fromLines(text)) !== toLines(value)) setText(toLines(value));

  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(fromLines(e.target.value));
        }}
        rows={4}
        className="w-full rounded-tk border border-stroke bg-surface px-3 py-2 font-mono text-xs text-ink"
      />
      <span className="mt-1 block text-xs text-faint">{hint} · one per line</span>
    </label>
  );
}
