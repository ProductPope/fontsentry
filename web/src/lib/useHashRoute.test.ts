import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useHashRoute } from "./useHashRoute";

afterEach(() => {
  window.location.hash = "";
});

describe("useHashRoute", () => {
  it("reads the current section from the hash", () => {
    window.location.hash = "/registry";
    const { result } = renderHook(() => useHashRoute());
    expect(result.current.route).toBe("registry");
  });

  it("falls back to the overview for an empty or unknown hash", () => {
    const { result } = renderHook(() => useHashRoute());
    expect(result.current.route).toBe("overview");

    act(() => {
      window.location.hash = "/no-such-section";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(result.current.route).toBe("overview");
  });

  it("navigate() updates the hash and the route", () => {
    const { result } = renderHook(() => useHashRoute());
    act(() => {
      result.current.navigate("backup");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(window.location.hash).toBe("#/backup");
    expect(result.current.route).toBe("backup");
  });
});
