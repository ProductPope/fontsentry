import { PrivacyText, VerdictBadge } from "../components/Badge";
import type { Finding } from "../lib/api";
import { cn } from "../lib/cn";
import { findingKey, worstVerdict, type Group } from "../lib/findings";
import { delivery, isPrivacyFlagged } from "../lib/privacy";
import { FindingDetail } from "./finding-detail";

function DeliveryBadge({ finding }: { finding: Finding }) {
  const d = delivery(finding);
  return (
    <span
      className={cn(
        "inline-block rounded-chip px-2 py-0.5 text-xs font-medium",
        d.flagged ? "bg-band-medium-bg text-band-medium" : "text-faint",
      )}
    >
      {/* Don't rely on colour/glyph alone (WCAG 1.4.1): carry the meaning in text. */}
      {d.flagged && <span className="sr-only">Third-party delivery, privacy concern: </span>}
      {d.flagged && (
        <span role="img" aria-label="warning">
          ⚠{" "}
        </span>
      )}
      {d.label}
    </span>
  );
}

// A family split into weights/styles: one summary row (worst verdict, shared
// owner, total domains) that expands to its variants.
export function GroupRows({
  group,
  isOpen,
  onToggle,
  expanded,
  onToggleFinding,
}: {
  group: Group;
  isOpen: boolean;
  onToggle: () => void;
  expanded: string | null;
  onToggleFinding: (key: string) => void;
}) {
  const verdict = worstVerdict(group.findings);
  const domains = new Set(group.findings.flatMap((f) => f.domains)).size;
  const owners = new Set(group.findings.map((f) => f.owner ?? ""));
  const owner = owners.size === 1 ? [...owners][0] || "—" : "—";
  // Representative delivery: prefer a privacy-flagged variant so the group row
  // still warns when any weight is served third-party.
  const rep = group.findings.find(isPrivacyFlagged) ?? group.findings[0]!;
  return (
    <>
      <tr className="border-t border-stroke bg-surface2/40">
        <td className="px-4 py-2">
          <button onClick={onToggle} aria-expanded={isOpen} className="text-left font-semibold">
            <span aria-hidden="true">{isOpen ? "▾ " : "▸ "}</span>
            {group.label}
            <span className="ml-2 text-xs font-normal text-faint">
              {group.findings.length} variants
            </span>
          </button>
        </td>
        <td className="px-4 py-2">{owner}</td>
        <td className="px-4 py-2">
          <DeliveryBadge finding={rep} />
        </td>
        <td className="px-4 py-2 font-mono tabular-nums">{domains}</td>
        <td className="px-4 py-2">
          <VerdictBadge verdict={verdict} />
        </td>
        <td className="px-4 py-2">
          <PrivacyText privacy={rep.privacy} />
        </td>
      </tr>
      {isOpen &&
        group.findings.map((f) => {
          const key = findingKey(f);
          return (
            <FindingRows
              key={key}
              finding={f}
              isOpen={expanded === key}
              onToggle={() => onToggleFinding(key)}
              indent
            />
          );
        })}
    </>
  );
}

// One finding's row, plus its explanation row when expanded.
export function FindingRows({
  finding,
  isOpen,
  onToggle,
  indent = false,
}: {
  finding: Finding;
  isOpen: boolean;
  onToggle: () => void;
  indent?: boolean;
}) {
  const detailId = `finding-detail-${findingKey(finding)}`;
  return (
    <>
      <tr className="border-t border-stroke">
        <td className={cn("px-4 py-2", indent && "pl-9")}>
          <button
            onClick={onToggle}
            aria-expanded={isOpen}
            aria-controls={detailId}
            className={cn("text-left", indent ? "font-normal text-muted" : "font-medium")}
          >
            <span aria-hidden="true">{isOpen ? "▾ " : "▸ "}</span>
            {finding.family}
          </button>
        </td>
        <td className="px-4 py-2">{finding.owner ?? "—"}</td>
        <td className="px-4 py-2">
          <DeliveryBadge finding={finding} />
        </td>
        <td className="px-4 py-2 font-mono tabular-nums">{finding.domains.length}</td>
        <td className="px-4 py-2">
          <VerdictBadge verdict={finding.license_verdict} />
        </td>
        <td className="px-4 py-2">
          <PrivacyText privacy={finding.privacy} />
        </td>
      </tr>
      {isOpen && (
        <tr id={detailId}>
          <td colSpan={6} className="p-0">
            <FindingDetail finding={finding} />
          </td>
        </tr>
      )}
    </>
  );
}
