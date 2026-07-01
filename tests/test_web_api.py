"""Web API tests via FastAPI TestClient. Scans run in demo mode — fully offline.

The client is used as a context manager so the app's event loop stays alive across
requests, letting the background scan task run.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fontsentry.web.server import create_app


@contextmanager
def _client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(reports_dir=tmp_path)) as client:
        yield client


def _run_demo_scan(client: TestClient) -> str:
    started = client.post("/api/scan", json={"mode": "demo"})
    assert started.status_code == 200
    job_id = started.json()["job_id"]

    deadline = time.time() + 20
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "done":
            assert job["run_id"]
            return str(job["run_id"])
        assert job["status"] != "error", job.get("error")
        time.sleep(0.05)
    raise AssertionError("scan job did not finish in time")


def test_health(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/health").json() == {"status": "ok"}


def test_scan_then_list_and_fetch(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        run_id = _run_demo_scan(client)

        runs = client.get("/api/runs").json()
        assert any(r["id"] == run_id for r in runs)

        report = client.get(f"/api/runs/{run_id}").json()
        families = {f["family"] for f in report["findings"]}
        assert "Atlas Grotesk Private" in families
        assert report["summary"]["open_findings"] >= 1


def test_run_not_found(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/runs/missing.report.json").status_code == 404


def test_run_id_traversal_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/runs/..%2f..%2fsecret").status_code in (400, 404)


def test_origin_guard_blocks_cross_origin(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        blocked = client.post(
            "/api/scan", json={"mode": "demo"}, headers={"Origin": "http://evil.example"}
        )
        assert blocked.status_code == 403

        allowed = client.post(
            "/api/scan", json={"mode": "demo"}, headers={"Origin": "http://localhost:5173"}
        )
        assert allowed.status_code == 200


def test_invalid_mode_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.post("/api/scan", json={"mode": "bogus"}).status_code == 400


def test_schedules_list_ok(tmp_path: Path) -> None:
    # Read-only; harmless on any OS (returns [] off Windows).
    with _client(tmp_path) as client:
        resp = client.get("/api/schedules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_create_schedule_unsupported_off_windows(tmp_path: Path) -> None:
    import sys

    if sys.platform == "win32":
        pytest.skip("would create a real scheduled task on Windows")
    with _client(tmp_path) as client:
        resp = client.post("/api/schedules", json={"name": "weekly-audit"})
        assert resp.status_code == 501
