import { Button } from "../components/Button";
import { Modal } from "../components/Modal";

// Restoring overwrites the workspace, so it always asks first.
interface RestoreConfirmProps {
  onCancel: () => void;
  onConfirm: () => void;
}

export function RestoreConfirm({ onCancel, onConfirm }: RestoreConfirmProps) {
  return (
    <Modal title="Restore this backup?" onClose={onCancel}>
      <p className="text-sm text-muted">
        This overwrites your current targets, licenses, and audits with the backup. Your current
        state is snapshotted first, so you can restore back to it.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={onConfirm}>Restore</Button>
      </div>
    </Modal>
  );
}
