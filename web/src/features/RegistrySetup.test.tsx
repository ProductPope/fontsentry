import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RegistryEntry } from "../lib/api";
import { RegistrySetup } from "./RegistrySetup";

const api = vi.hoisted(() => ({
  getRegistry: vi.fn(),
  getKnownFonts: vi.fn(),
  saveRegistry: vi.fn(),
  importRegistry: vi.fn(),
  importRegistryCsv: vi.fn(),
  uploadProof: vi.fn(),
  proofUrl: (name: string) => `/api/registry/proof/${name}`,
  registryCsvUrl: "/api/config/registry/export.csv",
}));
vi.mock("../lib/api", () => ({ api }));

function entry(over: Partial<RegistryEntry> = {}): RegistryEntry {
  return {
    owner: "Meridian Letterworks",
    family: "Atlas Grotesk",
    license_type: "Commercial — per domain",
    allowed_domains: ["example.com"],
    max_domains: 1,
    proof_path: null,
    invoice_path: null,
    valid_until: null,
    notes: null,
    ...over,
  };
}

function renderWith(entries: RegistryEntry[]) {
  api.getRegistry.mockResolvedValue({ entries });
  const notify = vi.fn();
  render(<RegistrySetup notify={notify} />);
  return notify;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getKnownFonts.mockResolvedValue([
    { family: "Harbor Serif", owner: "Northwind Type", source: "detected" },
  ]);
  // The server echoes what it saved.
  api.saveRegistry.mockImplementation(async (r: { entries: RegistryEntry[] }) => r);
});

describe("RegistrySetup", () => {
  it("lists the registry's licenses", async () => {
    renderWith([entry(), entry({ family: "Harbor Serif", allowed_domains: ["*"] })]);
    expect(await screen.findByText("Atlas Grotesk")).toBeInTheDocument();
    expect(screen.getByText("Harbor Serif")).toBeInTheDocument();
    expect(screen.getByText("any domain")).toBeInTheDocument();
  });

  it("offers example licenses only when the registry is empty", async () => {
    renderWith([]);
    fireEvent.click(await screen.findByRole("button", { name: "Insert examples" }));
    await waitFor(() => expect(api.saveRegistry).toHaveBeenCalledTimes(1));
    const saved = api.saveRegistry.mock.calls[0]![0] as { entries: RegistryEntry[] };
    expect(saved.entries.length).toBeGreaterThan(0);
  });

  it("adds a license through the form, filling the owner from a known family", async () => {
    const notify = renderWith([]);
    fireEvent.click(await screen.findByRole("button", { name: "Add license" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Font family"), {
      target: { value: "Harbor Serif" },
    });
    expect(within(dialog).getByLabelText(/^Owner/)).toHaveValue("Northwind Type");
    fireEvent.change(within(dialog).getByLabelText("License type"), {
      target: { value: "Commercial — unlimited" },
    });
    fireEvent.change(within(dialog).getByLabelText(/^Allowed domains/), {
      target: { value: "a.example, b.example" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save license" }));

    await waitFor(() => expect(notify).toHaveBeenCalledWith("License saved", "success"));
    const saved = api.saveRegistry.mock.calls[0]![0] as { entries: RegistryEntry[] };
    expect(saved.entries).toEqual([
      entry({
        owner: "Northwind Type",
        family: "Harbor Serif",
        license_type: "Commercial — unlimited",
        allowed_domains: ["a.example", "b.example"],
        max_domains: null,
      }),
    ]);
  });

  it("refuses to save a license without the required fields", async () => {
    renderWith([]);
    fireEvent.click(await screen.findByRole("button", { name: "Add license" }));
    fireEvent.click(screen.getByRole("button", { name: "Save license" }));
    expect(screen.getByRole("alert")).toHaveTextContent("needs an owner, font family");
    expect(api.saveRegistry).not.toHaveBeenCalled();
  });

  it("edits and deletes an existing license", async () => {
    renderWith([entry(), entry({ family: "Second" })]);
    fireEvent.click((await screen.findAllByRole("button", { name: "Edit" }))[0]!);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Font family")).toHaveValue("Atlas Grotesk");
    fireEvent.change(within(dialog).getByLabelText("Notes"), { target: { value: "renewed" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save license" }));
    await waitFor(() => expect(api.saveRegistry).toHaveBeenCalledTimes(1));
    const edited = api.saveRegistry.mock.calls[0]![0] as { entries: RegistryEntry[] };
    expect(edited.entries.map((e) => e.notes)).toEqual(["renewed", null]);

    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[1]!);
    await waitFor(() => expect(api.saveRegistry).toHaveBeenCalledTimes(2));
    const removed = api.saveRegistry.mock.calls[1]![0] as { entries: RegistryEntry[] };
    expect(removed.entries.map((e) => e.family)).toEqual(["Atlas Grotesk"]);
  });

  it("attaches an uploaded proof under the name the server stored", async () => {
    api.uploadProof.mockResolvedValue({ name: "invoice-1.pdf" });
    renderWith([]);
    fireEvent.click(await screen.findByRole("button", { name: "Add license" }));
    const input = screen.getByRole("dialog").querySelector('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [new File(["%PDF"], "invoice.pdf")] } });
    expect(await screen.findByRole("link", { name: "invoice-1.pdf" })).toBeInTheDocument();
  });

  it("merges an imported JSON registry and reports what changed", async () => {
    api.importRegistry.mockResolvedValue({
      registry: { entries: [entry({ family: "Imported" })] },
      errors: [],
      added: 1,
      replaced: 0,
    });
    const notify = renderWith([]);
    const input = await screen.findByLabelText("Import registry JSON file");
    const file = new File([JSON.stringify({ entries: [entry({ family: "Imported" })] })], "r.json");
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText("Imported")).toBeInTheDocument();
    expect(api.importRegistry).toHaveBeenCalledTimes(1);
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("1 added"), "success");
  });

  it("reports skipped CSV rows", async () => {
    api.importRegistryCsv.mockResolvedValue({
      registry: { entries: [] },
      errors: ["row 3: bad max_domains"],
      added: 0,
      replaced: 0,
    });
    const notify = renderWith([]);
    const input = await screen.findByLabelText("Import registry CSV file");
    fireEvent.change(input, { target: { files: [new File(["owner,family\n"], "r.csv")] } });
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(expect.stringContaining("row 3: bad max_domains"), "info"),
    );
  });
});
