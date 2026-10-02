import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DomainFont, DomainReport } from "../lib/api";
import { DomainsView } from "./DomainsView";

const api = vi.hoisted(() => ({ getFirstSeen: vi.fn() }));
vi.mock("../lib/api", () => ({ api }));

function font(over: Partial<DomainFont> = {}): DomainFont {
  return {
    family: "Beacon Sans",
    owner: "Public Glyphs",
    license_verdict: "ok",
    license_reason: "",
    privacy: "self_hosted",
    embeddings: ["self_hosted"],
    formats: ["woff2"],
    hosts: ["example.com"],
    assets: [{ host: "example.com", urls: ["https://example.com/f/beacon.woff2?v=1"] }],
    ...over,
  };
}

const DOMAINS: DomainReport[] = [
  {
    domain: "example.com",
    is_live: true,
    pages_scanned: 2,
    live_hosts: ["example.com", "blog.example.com"],
    subdomains: ["blog.example.com"],
    fonts: [
      font({ hosts: ["example.com", "blog.example.com"] }),
      font({
        family: "Atlas Grotesk",
        license_verdict: "violation",
        hosts: ["blog.example.com"],
        assets: [
          { host: "blog.example.com", urls: ["javascript:alert(1)", "https://x.example/b.woff"] },
        ],
      }),
    ],
  },
  {
    domain: "shop.example",
    is_live: true,
    pages_scanned: 1,
    live_hosts: ["shop.example"],
    subdomains: [],
    fonts: [font({ family: "Harbor Serif", hosts: ["shop.example"], assets: [] })],
  },
];

const bodyRows = () => screen.getAllByRole("row").slice(1);

beforeEach(() => {
  api.getFirstSeen.mockResolvedValue([
    { domain: "example.com", family: "Beacon Sans", first_seen: "2026-05-01T06:00:00Z" },
  ]);
});

describe("DomainsView", () => {
  it("explains an older report without domain data", () => {
    render(<DomainsView domains={[]} />);
    expect(screen.getByText(/no domain data/)).toBeInTheDocument();
  });

  it("lists one row per host and font, sorted, marking subdomains", () => {
    render(<DomainsView domains={DOMAINS} />);
    const rows = bodyRows().map((r) => r.textContent ?? "");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toMatch(/^blog\.example\.com\(subdomain\)Atlas Grotesk/);
    expect(rows[1]).toMatch(/^blog\.example\.com\(subdomain\)Beacon Sans/);
    expect(rows[2]).toMatch(/^example\.comBeacon Sans/);
    expect(rows[3]).toMatch(/^shop\.exampleHarbor Serif/);
  });

  it("links font files safely and shows when a font was first seen", async () => {
    render(<DomainsView domains={DOMAINS} source="demo" />);
    expect(screen.getByRole("link", { name: "beacon.woff2" })).toHaveAttribute(
      "href",
      "https://example.com/f/beacon.woff2?v=1",
    );
    // A non-http URL is shown as text, never as a link; extra files are counted.
    expect(screen.getByText("javascript:alert(1) +1")).not.toHaveAttribute("href");
    // First seen is per (domain, family): both hosts of example.com show it.
    expect(await screen.findAllByText("2026-05-01")).toHaveLength(2);
    expect(api.getFirstSeen).toHaveBeenCalledWith("demo");
  });

  it("filters by domain and by license verdict", async () => {
    render(<DomainsView domains={DOMAINS} />);
    fireEvent.change(screen.getByLabelText("Domain"), { target: { value: "shop.example" } });
    expect(bodyRows()).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("Domain"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("License"), { target: { value: "violation" } });
    await waitFor(() => expect(bodyRows()).toHaveLength(1));
    expect(bodyRows()[0]).toHaveTextContent("Atlas Grotesk");
    fireEvent.change(screen.getByLabelText("Domain"), { target: { value: "shop.example" } });
    expect(screen.getByText("No fonts match the filters.")).toBeInTheDocument();
  });
});
