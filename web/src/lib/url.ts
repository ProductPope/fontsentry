// URLs shown in the UI come from crawled pages (font-file src, page URLs), i.e.
// untrusted input. Only render them as links when they are http(s); a
// `javascript:` / `data:` URL rendered as an href would execute on click.
export function safeHref(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}
