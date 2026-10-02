import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api request", () => {
  it("returns the parsed JSON body on success", async () => {
    mockFetch(json([{ id: "fontsentry-1.report.json" }]));
    await expect(api.getRuns()).resolves.toEqual([{ id: "fontsentry-1.report.json" }]);
  });

  it("surfaces the server's detail message on an error", async () => {
    mockFetch(json({ detail: "an audit is already running" }, { status: 409 }));
    await expect(api.startScan("demo")).rejects.toThrow("an audit is already running");
  });

  it("falls back to the status text for a non-JSON error body", async () => {
    mockFetch(new Response("boom", { status: 500, statusText: "Internal Server Error" }));
    await expect(api.getRegistry()).rejects.toThrow("Internal Server Error");
  });

  it("sends JSON with the request options it was given", async () => {
    const fetchMock = mockFetch(json({ job_id: "abc" }));
    await api.startScan("real", true, 5);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/scan");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      mode: "real",
      discover_subdomains: true,
      max_pages_per_domain: 5,
    });
  });

  it("lets a caller override the JSON content type", async () => {
    const fetchMock = mockFetch(json({ registry: { entries: [] }, added: 0, replaced: 0 }));
    await api.importRegistryCsv("owner,family\n");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toEqual({ "Content-Type": "text/csv" });
  });

  it("encodes ids placed in the path", async () => {
    const fetchMock = mockFetch(json({}));
    await api.getJob("a/b");
    const [path] = fetchMock.mock.calls[0] as [string];
    expect(path).toBe("/api/jobs/a%2Fb");
  });
});

describe("api.uploadProof", () => {
  it("returns the stored name (which may differ from the upload's)", async () => {
    mockFetch(json({ name: "invoice-1.pdf" }));
    const file = new File(["%PDF"], "invoice.pdf", { type: "application/pdf" });
    await expect(api.uploadProof(file)).resolves.toEqual({ name: "invoice-1.pdf" });
  });

  it("surfaces the server's detail message on an error", async () => {
    mockFetch(json({ detail: "unsupported file type" }, { status: 400 }));
    const file = new File(["MZ"], "tool.exe");
    await expect(api.uploadProof(file)).rejects.toThrow("unsupported file type");
  });
});
