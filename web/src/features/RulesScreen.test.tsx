import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RulesConfig } from "../lib/api";
import { RulesScreen } from "./RulesScreen";

const api = vi.hoisted(() => ({ getRules: vi.fn(), saveRules: vi.fn() }));
vi.mock("../lib/api", () => ({ api }));

const RULES: RulesConfig = {
  open_license_patterns: ["SIL Open Font License"],
  free_owners: ["Public Glyphs"],
  open_families: [],
  paid_tier_families: [],
  self_host_prohibited: { owners: ["Cloud Type"], families: [] },
  paid_cdns: ["adobe_fonts"],
  desktop_formats: ["ttf", "otf"],
  subset_max_glyphs: 60,
};

beforeEach(() => {
  vi.clearAllMocks();
  api.getRules.mockResolvedValue(RULES);
  api.saveRules.mockImplementation(async (r: RulesConfig) => r);
});

describe("RulesScreen", () => {
  it("shows each classification list one item per line", async () => {
    render(<RulesScreen notify={vi.fn()} />);
    expect(await screen.findByLabelText(/^Desktop formats/)).toHaveValue("ttf\notf");
    expect(screen.getByLabelText(/^Self-host prohibited — owners/)).toHaveValue("Cloud Type");
  });

  it("saves edited lists (trimmed, blanks dropped) and the glyph threshold", async () => {
    const notify = vi.fn();
    render(<RulesScreen notify={notify} />);
    fireEvent.change(await screen.findByLabelText(/^Free owners/), {
      target: { value: " Public Glyphs \n\nNorthwind Type" },
    });
    fireEvent.change(screen.getByLabelText(/^Self-host prohibited — families/), {
      target: { value: "Atlas Grotesk" },
    });
    fireEvent.change(screen.getByLabelText("Subset max glyphs (evidence)"), {
      target: { value: "80" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save classification" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("Saved classification config", "success"));
    expect(api.saveRules).toHaveBeenCalledWith({
      ...RULES,
      free_owners: ["Public Glyphs", "Northwind Type"],
      self_host_prohibited: { owners: ["Cloud Type"], families: ["Atlas Grotesk"] },
      subset_max_glyphs: 80,
    });
  });
});
