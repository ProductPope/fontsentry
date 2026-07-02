import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { useHashRoute } from "../lib/useHashRoute";

// First-run guidance, shown on Overview until the first audit exists. The
// non-technical user lands here in the browser (Claude Code started the app),
// so it must point the way with no jargon.
export function GettingStarted() {
  const { navigate } = useHashRoute();
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">Getting started</h2>
        <p className="mt-1 text-sm text-muted">
          FontSentry checks the fonts on your websites and flags the ones worth reviewing for
          licensing. Three steps:
        </p>
      </div>

      <ol className="space-y-3">
        <Step n={1} title="Add your websites">
          The domains you want to check.
          <div className="mt-2">
            <Button variant="secondary" onClick={() => navigate("targets")}>
              Add websites
            </Button>
          </div>
        </Step>
        <Step n={2} title="Run an audit">
          Use <strong>Start audit</strong> at the top-right. Not ready with your real sites yet?
          Choose <strong>demo</strong> to see how it works on sample data.
        </Step>
        <Step n={3} title="Read the results">
          Each font gets a risk band — <span className="font-medium text-band-high">High</span>{" "}
          / <span className="font-medium text-band-medium">Medium</span> /{" "}
          <span className="font-medium text-band-low">Low</span>. Open a row to see why it's
          flagged and what to do about it.
        </Step>
      </ol>

      <p className="text-xs text-faint">
        Everything stays on this computer — scans and settings never leave your machine.
      </p>
    </Card>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent font-mono text-xs font-semibold text-accent-fg">
        {n}
      </span>
      <div className="text-sm">
        <div className="font-medium">{title}</div>
        <div className="text-muted">{children}</div>
      </div>
    </li>
  );
}
