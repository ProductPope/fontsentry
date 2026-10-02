import { Select } from "../components/Select";
import { TextInput } from "../components/TextInput";
import type { LicenseVerdict } from "../lib/api";
import { cn } from "../lib/cn";
import type { FindingFilters, Focus } from "../lib/findings";

const FOCUS_CHIPS: { id: Focus; label: string }[] = [
  { id: "action", label: "Needs action" },
  { id: "privacy", label: "Privacy (GDPR)" },
  { id: "all", label: "All" },
];

interface FindingsFiltersProps {
  filters: FindingFilters;
  onChange: (filters: FindingFilters) => void;
  grouped: boolean;
  onGrouped: (grouped: boolean) => void;
}

// Toolbar above the findings table: focus chips, search, license filter, grouping.
export function FindingsFilters({ filters, onChange, grouped, onGrouped }: FindingsFiltersProps) {
  const set = (patch: Partial<FindingFilters>) => onChange({ ...filters, ...patch });
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div
        role="group"
        aria-label="Filter findings"
        className="flex rounded-tk border border-stroke bg-surface2 p-0.5"
      >
        {FOCUS_CHIPS.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => set({ focus: c.id })}
            aria-pressed={filters.focus === c.id}
            className={cn(
              "rounded-chip px-3 py-1 text-sm font-medium transition-colors",
              filters.focus === c.id
                ? "bg-surface text-ink shadow-tk"
                : "text-muted hover:text-ink",
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium">Search</span>
          <TextInput
            value={filters.search}
            onChange={(e) => set({ search: e.target.value })}
            placeholder="font or owner"
            aria-label="Search findings"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">License</span>
          <Select
            value={filters.verdict}
            onChange={(e) => set({ verdict: e.target.value as LicenseVerdict | "all" })}
          >
            <option value="all">all</option>
            <option value="violation">violation</option>
            <option value="needs_check">needs check</option>
            <option value="ok">ok</option>
          </Select>
        </label>
        <label className="flex items-center gap-1.5 pb-2 text-sm">
          <input type="checkbox" checked={grouped} onChange={(e) => onGrouped(e.target.checked)} />
          <span className="font-medium">Group variants</span>
        </label>
      </div>
    </div>
  );
}
