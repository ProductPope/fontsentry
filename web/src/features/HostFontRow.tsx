import { PrivacyText, VerdictBadge } from "../components/Badge";
import type { HostRow } from "../lib/domains";
import { assetLabel } from "../lib/domains";
import { safeHref } from "../lib/url";

// One (host, font) row of the Domains table. Font-file URLs come from crawled
// pages, so only http(s) URLs become links (safeHref); others show as text.
export function HostFontRow({ row: r, firstSeen }: { row: HostRow; firstSeen?: string }) {
  const href = safeHref(r.assetUrls[0]);
  return (
    <tr className="border-t border-stroke">
      <td className="px-4 py-2">
        <span className="font-mono text-xs">{r.host}</span>
        {r.isSubdomain && <span className="ml-1 text-faint">(subdomain)</span>}
      </td>
      <td className="px-4 py-2 font-medium">{r.family}</td>
      <td className="px-4 py-2">{r.owner ?? "—"}</td>
      <td className="px-4 py-2 font-mono text-xs">{r.embeddings.join(", ") || "—"}</td>
      <td className="px-4 py-2 font-mono text-xs">{r.formats.join(", ") || "—"}</td>
      <td className="max-w-[16rem] truncate px-4 py-2 font-mono text-xs text-muted">
        {r.assetUrls.length === 0 ? (
          "—"
        ) : href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            title={r.assetUrls.join("\n")}
            className="text-accent underline"
          >
            {assetLabel(r.assetUrls)}
          </a>
        ) : (
          <span title={r.assetUrls.join("\n")}>{assetLabel(r.assetUrls)}</span>
        )}
      </td>
      <td className="px-4 py-2">
        <VerdictBadge verdict={r.verdict} />
      </td>
      <td className="px-4 py-2">
        <PrivacyText privacy={r.privacy} />
      </td>
      <td className="px-4 py-2 font-mono text-xs text-muted">{firstSeen?.slice(0, 10) ?? "—"}</td>
    </tr>
  );
}
