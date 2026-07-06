"""Whole-workspace backup/restore: round-trip, zip-slip guard, snapshots."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fontsentry.web.workspace import (
    WorkspaceError,
    build_workspace_zip,
    list_backups,
    read_backup,
    restore_workspace_zip,
    write_snapshot,
)

NOW = datetime(2026, 7, 6, 9, 45, 0, tzinfo=UTC)


def _seed(root: Path) -> tuple[Path, Path, Path]:
    config, registry, reports = root / "config", root / "registry", root / "reports"
    (config).mkdir()
    (registry / "proofs").mkdir(parents=True)
    (reports).mkdir()
    (config / "targets.yaml").write_text("targets: [example.com]\n", encoding="utf-8")
    (registry / "licenses.yaml").write_text("entries: []\n", encoding="utf-8")
    (registry / "proofs" / "acme.pdf").write_bytes(b"%PDF-1.4 fake")
    (reports / "run.report.json").write_text('{"findings": []}', encoding="utf-8")
    return config, registry, reports


def test_backup_restore_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    config, registry, reports = _seed(src)
    data = build_workspace_zip(config, registry, reports)

    dst = tmp_path / "dst"
    d_config, d_registry, d_reports = dst / "config", dst / "registry", dst / "reports"
    restore_workspace_zip(data, d_config, d_registry, d_reports)

    assert (d_config / "targets.yaml").read_text(encoding="utf-8") == "targets: [example.com]\n"
    assert (d_registry / "proofs" / "acme.pdf").read_bytes() == b"%PDF-1.4 fake"
    assert (d_reports / "run.report.json").exists()


def test_restore_overwrites_but_keeps_local_extras(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    config, registry, reports = _seed(src)
    data = build_workspace_zip(config, registry, reports)

    dst = tmp_path / "dst"
    (dst / "config").mkdir(parents=True)
    (dst / "config" / "targets.yaml").write_text("old\n", encoding="utf-8")
    (dst / "config" / "local-only.yaml").write_text("keep\n", encoding="utf-8")
    restore_workspace_zip(data, dst / "config", dst / "registry", dst / "reports")

    assert (dst / "config" / "targets.yaml").read_text(encoding="utf-8").startswith("targets")
    assert (dst / "config" / "local-only.yaml").exists()  # not in backup -> untouched


def test_restore_rejects_non_workspace_zip(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("config/targets.yaml", "x")  # no manifest
    with pytest.raises(WorkspaceError, match="manifest"):
        restore_workspace_zip(buffer.getvalue(), tmp_path / "c", tmp_path / "r", tmp_path / "rep")


def test_restore_rejects_zip_slip(tmp_path: Path) -> None:
    import json

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": 1}))
        archive.writestr("config/../../evil.txt", "pwned")
    with pytest.raises(WorkspaceError, match="unsafe path"):
        restore_workspace_zip(buffer.getvalue(), tmp_path / "c", tmp_path / "r", tmp_path / "rep")


def test_restore_rejects_bad_zip(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="valid zip"):
        restore_workspace_zip(b"not a zip", tmp_path / "c", tmp_path / "r", tmp_path / "rep")


def _manifest_zip() -> tuple[io.BytesIO, zipfile.ZipFile]:
    import json

    buffer = io.BytesIO()
    archive = zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED)
    archive.writestr("manifest.json", json.dumps({"version": 1}))
    return buffer, archive


def test_restore_rejects_zip_bomb_by_declared_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A tiny compressed payload expanding past the decompression cap must be
    # rejected before anything is extracted (limit lowered to keep the test fast;
    # zeros compress ~1000:1, so the real 500 MB cap fits in a ~0.5 MB upload).
    from fontsentry.web import workspace

    monkeypatch.setattr(workspace, "_MAX_TOTAL_UNCOMPRESSED", 1024)
    buffer, archive = _manifest_zip()
    with archive:
        archive.writestr("config/huge.yaml", b"\0" * 2048)
    with pytest.raises(WorkspaceError, match="decompress"):
        restore_workspace_zip(buffer.getvalue(), tmp_path / "c", tmp_path / "r", tmp_path / "rep")
    assert not (tmp_path / "c").exists()  # nothing was written


def test_restore_rejects_too_many_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fontsentry.web import workspace

    monkeypatch.setattr(workspace, "_MAX_ENTRIES", 2)
    buffer, archive = _manifest_zip()
    with archive:
        for i in range(3):
            archive.writestr(f"config/f{i}.yaml", b"x")
    with pytest.raises(WorkspaceError, match="entries"):
        restore_workspace_zip(buffer.getvalue(), tmp_path / "c", tmp_path / "r", tmp_path / "rep")


def test_unsafe_entry_rejects_before_any_write(tmp_path: Path) -> None:
    # Path validation is a pre-pass: an unsafe entry anywhere in the archive
    # rejects the whole backup, never leaving a half-restored workspace.
    buffer, archive = _manifest_zip()
    with archive:
        archive.writestr("config/good.yaml", "ok")
        archive.writestr("config/../../evil.txt", "pwned")
    with pytest.raises(WorkspaceError, match="unsafe path"):
        restore_workspace_zip(buffer.getvalue(), tmp_path / "c", tmp_path / "r", tmp_path / "rep")
    assert not (tmp_path / "c" / "good.yaml").exists()


def test_snapshot_list_and_read(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    info = write_snapshot(backups, b"PK-fake-zip", NOW)
    assert info.name == "fontsentry-workspace-20260706T094500Z.zip"

    listed = list_backups(backups)
    assert [b.name for b in listed] == [info.name]
    assert read_backup(backups, info.name) == b"PK-fake-zip"


def test_read_backup_rejects_bad_name(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="invalid backup name"):
        read_backup(tmp_path, "../etc/passwd")
