import { Button } from "../components/Button";

export type ScanMode = "real" | "demo";

// Opens the run-audit settings modal (source, subdomains, page cap, ETA).
export function ScanControls({ onOpen, running }: { onOpen: () => void; running: boolean }) {
  return (
    <Button onClick={onOpen} disabled={running}>
      {running ? "Auditing…" : "Start audit"}
    </Button>
  );
}
