import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BackupScreen } from "./BackupScreen";

const api = vi.hoisted(() => ({
  listBackups: vi.fn(),
  snapshotWorkspace: vi.fn(),
  restoreBackup: vi.fn(),
  importWorkspace: vi.fn(),
  workspaceExportUrl: "/api/workspace/export",
  backupDownloadUrl: (name: string) => `/api/workspace/backups/${name}`,
}));
vi.mock("../lib/api", () => ({ api }));

const BACKUP = {
  name: "fontsentry-workspace-20260601T060000Z.zip",
  size_bytes: 3 * 1024 * 1024 + 200 * 1024,
  created_at: "2026-06-01T06:00:00Z",
};

function renderBackup() {
  const notify = vi.fn();
  render(<BackupScreen notify={notify} />);
  return notify;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.listBackups.mockResolvedValue([BACKUP]);
});

describe("BackupScreen", () => {
  it("lists snapshots with their size", async () => {
    renderBackup();
    expect(await screen.findByText(BACKUP.name)).toBeInTheDocument();
    expect(screen.getByText(/3\.2 MB/)).toBeInTheDocument();
  });

  it("says so when there are no snapshots", async () => {
    api.listBackups.mockResolvedValue([]);
    renderBackup();
    expect(await screen.findByText(/No snapshots yet/)).toBeInTheDocument();
  });

  it("saves a snapshot and refreshes the list", async () => {
    api.snapshotWorkspace.mockResolvedValue({ ...BACKUP, name: "new.zip" });
    const notify = renderBackup();
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("Snapshot saved — new.zip", "success"));
    expect(api.listBackups).toHaveBeenCalledTimes(2);
  });

  it("restores a snapshot only after confirmation", async () => {
    api.restoreBackup.mockResolvedValue({ restored: BACKUP.name });
    const notify = renderBackup();
    fireEvent.click(await screen.findByRole("button", { name: "Restore" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(api.restoreBackup).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(api.restoreBackup).toHaveBeenCalledWith(BACKUP.name));
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(
        "Restored — the previous state was snapshotted first",
        "success",
      ),
    );
  });

  it("restores from an uploaded file after confirmation, surfacing errors", async () => {
    api.importWorkspace.mockRejectedValue(new Error("not a valid zip archive"));
    const notify = renderBackup();
    const file = new File(["PK"], "backup.zip");
    fireEvent.change(screen.getByLabelText("Restore workspace from a backup file"), {
      target: { files: [file] },
    });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(api.importWorkspace).toHaveBeenCalledWith(file));
    await waitFor(() => expect(notify).toHaveBeenCalledWith("not a valid zip archive", "error"));
  });
});
