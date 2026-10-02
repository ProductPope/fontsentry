import { describe, expect, it } from "vitest";
import type { DomainReport, Finding, RunReport } from "./api";
import { countByVerdict, deltaText, openCount, overviewStats } from "./overview";

const f = (license_verdict: Finding["license_verdict"], privacy: Finding["privacy"] = "self_hosted") =>
  ({ license_verdict, privacy, embeddings: [] }) as unknown as Finding;

const d = (is_live: boolean, verdicts: Finding["license_verdict"][]) =>
  ({ is_live, fonts: verdicts.map((license_verdict) => ({ license_verdict })) }) as unknown as DomainReport;

const report = (findings: Finding[], domains: DomainReport[] = []) =>
  ({ findings, domains }) as unknown as RunReport;

describe("overview helpers", () => {
  it("counts findings per verdict", () => {
    const counts = countByVerdict(report([f("ok"), f("violation"), f("ok")]));
    expect(counts).toEqual({ violation: 1, needs_check: 0, ok: 2 });
    expect(openCount(counts)).toBe(1);
  });

  it("formats deltas", () => {
    expect(deltaText(3)).toBe("↑3");
    expect(deltaText(-2)).toBe("↓2");
    expect(deltaText(0)).toBe("±0");
  });

  it("derives portfolio and privacy stats", () => {
    const stats = overviewStats(
      report(
        [f("ok", "third_party_api"), f("ok", "mixed"), f("ok")],
        [d(true, ["ok"]), d(true, ["ok", "needs_check"]), d(false, [])],
      ),
    );
    expect(stats).toMatchObject({ domains: 3, live: 2, unreachable: 1, clean: 2, privacyFlagged: 2 });
  });
});
