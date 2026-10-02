import { describe, expect, it } from "vitest";
import type { DomainReport } from "./api";
import { assetLabel, firstSeenKey, toRows } from "./domains";

describe("domains helpers", () => {
  it("labels font files by filename, counting extras", () => {
    expect(assetLabel([])).toBe("—");
    expect(assetLabel(["https://a.example/f/x.woff2?v=2"])).toBe("x.woff2");
    expect(assetLabel(["https://a.example/f/x.woff2", "https://a.example/y.woff"])).toBe(
      "x.woff2 +1",
    );
    expect(assetLabel(["https://a.example/"])).toBe("https://a.example/");
  });

  it("keys first-seen by domain and family without collisions", () => {
    expect(firstSeenKey("a b", "c")).not.toBe(firstSeenKey("a", "b c"));
  });

  it("pivots fonts into sorted host rows with their own assets", () => {
    const domains = [
      {
        domain: "example.com",
        subdomains: ["blog.example.com"],
        fonts: [
          {
            family: "Z",
            owner: null,
            license_verdict: "ok",
            privacy: "self_hosted",
            embeddings: [],
            formats: [],
            hosts: ["example.com", "blog.example.com"],
            assets: [{ host: "blog.example.com", urls: ["u"] }],
          },
          {
            family: "A",
            owner: null,
            license_verdict: "ok",
            privacy: "self_hosted",
            embeddings: [],
            formats: [],
            hosts: ["example.com"],
            assets: [],
          },
        ],
      },
    ] as unknown as DomainReport[];
    const rows = toRows(domains);
    expect(rows.map((r) => `${r.host}/${r.family}`)).toEqual([
      "blog.example.com/Z",
      "example.com/A",
      "example.com/Z",
    ]);
    expect(rows[0]).toMatchObject({ isSubdomain: true, assetUrls: ["u"], domain: "example.com" });
    expect(rows[2]!.assetUrls).toEqual([]);
  });
});
