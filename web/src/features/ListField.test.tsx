import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ListField } from "./ListField";

function Harness({ initial, onChange }: { initial: string[]; onChange: (v: string[]) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <ListField
      label="Formats"
      hint="hint"
      value={value}
      onChange={(v) => {
        setValue(v);
        onChange(v);
      }}
    />
  );
}

describe("ListField", () => {
  it("keeps a typed newline so a new item can be added from the keyboard", () => {
    const onChange = vi.fn();
    render(<Harness initial={["ttf"]} onChange={onChange} />);
    const box = screen.getByLabelText(/^Formats/);
    fireEvent.change(box, { target: { value: "ttf\n" } });
    expect(box).toHaveValue("ttf\n");
    fireEvent.change(box, { target: { value: "ttf\n otf " } });
    expect(onChange).toHaveBeenLastCalledWith(["ttf", "otf"]);
  });

  it("shows a new value from outside (e.g. after loading or saving)", () => {
    const { rerender } = render(
      <ListField label="Formats" hint="hint" value={["ttf"]} onChange={vi.fn()} />,
    );
    rerender(<ListField label="Formats" hint="hint" value={["woff", "eot"]} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/^Formats/)).toHaveValue("woff\neot");
  });
});
