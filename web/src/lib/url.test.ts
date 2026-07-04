import { describe, expect, it } from "vitest";
import { safeHref } from "./url";

describe("safeHref", () => {
  it("passes through http(s) URLs", () => {
    expect(safeHref("https://example.com/a.woff2")).toBe("https://example.com/a.woff2");
    expect(safeHref("http://example.com/")).toBe("http://example.com/");
  });

  it("rejects dangerous or non-http schemes", () => {
    expect(safeHref("javascript:alert(1)")).toBeNull();
    expect(safeHref("data:font/woff2;base64,AAAA")).toBeNull();
    expect(safeHref("file:///etc/passwd")).toBeNull();
  });

  it("rejects empty / unparseable / relative", () => {
    expect(safeHref(null)).toBeNull();
    expect(safeHref(undefined)).toBeNull();
    expect(safeHref("")).toBeNull();
    expect(safeHref("/relative/path")).toBeNull();
  });
});
