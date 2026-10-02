"""Whole-workspace backup and restore.

Everything already persists to disk per edit (targets, registry, reports); this
bundles those three roots into one portable zip the operator can back up, move
between machines, or roll back to. Backups live in a gitignored ``backups/`` folder
so they never leave the machine.

Restore is overwrite-merge (files in the backup replace their on-disk copies; local
files absent from the backup are left alone). It is guarded against zip-slip and
always paired with an automatic pre-restore snapshot by the caller.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

_MANIFEST = "manifest.json"
_MANIFEST_VERSION = 1
# arcname prefix -> which create_app directory it maps to.
_PREFIXES = ("config", "registry", "reports")
_NAME_RE = re.compile(r"^fontsentry-workspace-\d{8}T\d{6}Z\.zip$")
# Zip-bomb guards: a restore payload is user-supplied ("a backup someone sent
# me"), so bound what it may decompress to before writing anything.
_MAX_ENTRIES = 10_000
_MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024  # 500 MB across all entries


class WorkspaceError(Exception):
    """Raised when a backup is malformed or unsafe to restore."""


class BackupInfo(BaseModel):
    name: str
    size_bytes: int
    created_at: str  # ISO 8601, from the file's mtime


def _roots(config_dir: Path, registry_dir: Path, reports_dir: Path) -> dict[str, Path]:
    return {"config": config_dir, "registry": registry_dir, "reports": reports_dir}


def build_workspace_zip(config_dir: Path, registry_dir: Path, reports_dir: Path) -> bytes:
    """Bundle config + registry (incl. proofs) + reports into a zip."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = {
            "version": _MANIFEST_VERSION,
            "tool": "fontsentry",
            "created_at": datetime.now(UTC).isoformat(),
            "roots": list(_PREFIXES),
        }
        archive.writestr(_MANIFEST, json.dumps(manifest, indent=2))
        for prefix, root in _roots(config_dir, registry_dir, reports_dir).items():
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
    return buffer.getvalue()


def validate_backup(data: bytes) -> zipfile.ZipFile:
    """Open ``data`` as a FontSentry backup, raising ``WorkspaceError`` if it
    isn't one. Cheap (no extraction), so callers can validate an upload *before*
    taking the pre-restore snapshot — a garbage payload must not leave one."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise WorkspaceError("not a valid zip archive") from exc
    if _MANIFEST not in archive.namelist():
        archive.close()
        raise WorkspaceError("missing manifest — not a FontSentry workspace backup")
    try:
        manifest = json.loads(archive.read(_MANIFEST))
    except ValueError as exc:
        archive.close()
        raise WorkspaceError("unreadable manifest") from exc
    if manifest.get("version") != _MANIFEST_VERSION:
        archive.close()
        raise WorkspaceError(f"unsupported backup version: {manifest.get('version')!r}")
    return archive


def restore_workspace_zip(
    data: bytes, config_dir: Path, registry_dir: Path, reports_dir: Path
) -> None:
    """Extract a workspace backup over the three roots, guarding against zip-slip."""
    roots = _roots(config_dir, registry_dir, reports_dir)
    with validate_backup(data) as archive:
        members = [i for i in archive.infolist() if i.filename != _MANIFEST]
        if len(members) > _MAX_ENTRIES:
            raise WorkspaceError(f"backup has more than {_MAX_ENTRIES} entries — refusing")
        declared = sum(info.file_size for info in members)
        if declared > _MAX_TOTAL_UNCOMPRESSED:
            raise WorkspaceError(
                "backup would decompress past the "
                f"{_MAX_TOTAL_UNCOMPRESSED // (1024 * 1024)} MB limit — refusing"
            )

        # Validate every destination before writing anything: an unsafe entry
        # must reject the whole backup, not leave a half-restored workspace.
        writes: list[tuple[zipfile.ZipInfo, Path]] = []
        for info in members:
            name = info.filename
            if name.endswith("/"):
                continue
            prefix, _, rel = name.partition("/")
            root = roots.get(prefix)
            if root is None or not rel:
                continue  # ignore anything outside the known roots
            destination = (root / rel).resolve()
            if not destination.is_relative_to(root.resolve()):
                raise WorkspaceError(f"unsafe path in backup: {name}")
            writes.append((info, destination))

        for info, destination in writes:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(info))


def snapshot_filename(now: datetime) -> str:
    return f"fontsentry-workspace-{now.strftime('%Y%m%dT%H%M%SZ')}.zip"


def _backup_info(path: Path) -> BackupInfo:
    stat = path.stat()
    created = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
    return BackupInfo(name=path.name, size_bytes=stat.st_size, created_at=created)


# Snapshots are full workspace copies (reports included), so an unbounded
# backups/ directory silently eats disk — keep the newest N and prune the rest.
_MAX_BACKUPS = 10


def write_snapshot(
    backups_dir: Path, data: bytes, now: datetime, *, keep: int = _MAX_BACKUPS
) -> BackupInfo:
    backups_dir.mkdir(parents=True, exist_ok=True)
    path = backups_dir / snapshot_filename(now)
    path.write_bytes(data)
    # Timestamped names sort chronologically, so "newest first" is a name sort.
    for stale in sorted(backups_dir.glob("fontsentry-workspace-*.zip"), reverse=True)[keep:]:
        stale.unlink(missing_ok=True)
    return _backup_info(path)


def list_backups(backups_dir: Path) -> list[BackupInfo]:
    if not backups_dir.is_dir():
        return []
    paths = sorted(backups_dir.glob("fontsentry-workspace-*.zip"), reverse=True)
    return [_backup_info(path) for path in paths]


def read_backup(backups_dir: Path, name: str) -> bytes:
    # The name is validated against the fixed pattern, so it can't traverse out of
    # backups_dir (no separators or `..` survive the regex).
    if not _NAME_RE.match(name):
        raise WorkspaceError("invalid backup name")
    path = backups_dir / name
    if not path.is_file():
        raise WorkspaceError("backup not found")
    return path.read_bytes()
