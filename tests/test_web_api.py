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
def _client(
    tmp_path: Path,
    *,
    config_dir: Path | None = None,
    registry_dir: Path | None = None,
) -> Iterator[TestClient]:
    # Only override config/registry dirs when a test needs isolation (the config
    # endpoints write files). Demo scans read rules from the real repo config, so
    # the default must fall through to create_app's own defaults.
    extra: dict[str, Path] = {}
    if config_dir is not None:
        extra["config_dir"] = config_dir
    if registry_dir is not None:
        extra["registry_dir"] = registry_dir
    with TestClient(create_app(reports_dir=tmp_path, **extra)) as client:
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


def test_targets_empty_then_roundtrip(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    with _client(tmp_path, config_dir=config_dir) as client:
        assert client.get("/api/config/targets").json() == {"targets": []}

        payload = {"targets": [{"domain": "Example.com", "subdomain_seeds": ["blog.example.com"]}]}
        put = client.put("/api/config/targets", json=payload)
        assert put.status_code == 200
        # Domain is normalized (scheme-stripped, lowercased) by the model.
        assert put.json()["targets"][0]["domain"] == "example.com"

        # It was persisted to the real (gitignored) file, not the example.
        assert (config_dir / "targets.yaml").exists()
        assert client.get("/api/config/targets").json()["targets"][0]["domain"] == "example.com"


def test_targets_invalid_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.put("/api/config/targets", json={"targets": [{"subdomain_seeds": []}]})
        assert resp.status_code == 422


def test_registry_roundtrip_preserves_optional_fields(tmp_path: Path) -> None:
    registry_dir = tmp_path / "registry"
    with _client(tmp_path, registry_dir=registry_dir) as client:
        assert client.get("/api/config/registry").json() == {"entries": []}

        payload = {
            "entries": [
                {
                    "owner": "Meridian Letterworks",
                    "family": "Atlas Grotesk Private",
                    "license_type": "Web, single domain",
                    "allowed_domains": ["example.com"],
                    "max_domains": 1,
                    "valid_until": "2027-12-31",
                    "notes": "renew before expiry",
                }
            ]
        }
        put = client.put("/api/config/registry", json=payload)
        assert put.status_code == 200
        assert (registry_dir / "licenses.yaml").exists()

        got = client.get("/api/config/registry").json()["entries"][0]
        assert got["family"] == "Atlas Grotesk Private"
        assert got["max_domains"] == 1
        assert got["valid_until"] == "2027-12-31"


def test_registry_invalid_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.put(
            "/api/config/registry",
            json={"entries": [{"owner": "X", "license_type": "Web"}]},  # missing family
        )
        assert resp.status_code == 422


_RULES_PAYLOAD = {
    "scoring": {"max_raw": 90, "bands": {"medium": 30, "high": 60}},
    "rules": [
        {
            "id": "desktop-format-on-web",
            "description": "Desktop font on the web.",
            "weight": 30,
            "confidence": 0.85,
            "when": {"type": "format_on_web", "params": {"formats": ["ttf", "otf"]}},
        }
    ],
}


def test_rules_get_falls_back_to_example(tmp_path: Path) -> None:
    # No config_dir override -> uses the repo config dir, which has rules.example.yaml.
    with _client(tmp_path) as client:
        resp = client.get("/api/config/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["scoring"]["max_raw"] > 0
        assert body["scoring"]["bands"]["high"] >= body["scoring"]["bands"]["medium"]
        assert len(body["rules"]) >= 1
        assert all("weight" in r and "confidence" in r for r in body["rules"])


def test_rules_roundtrip(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    with _client(tmp_path, config_dir=config_dir) as client:
        put = client.put("/api/config/rules", json=_RULES_PAYLOAD)
        assert put.status_code == 200

        # Persisted to the real (gitignored) file, then read back.
        assert (config_dir / "rules.yaml").exists()
        got = client.get("/api/config/rules").json()
        assert got["scoring"]["bands"]["medium"] == 30
        assert got["rules"][0]["id"] == "desktop-format-on-web"
        assert got["rules"][0]["weight"] == 30


def test_rules_invalid_confidence_rejected(tmp_path: Path) -> None:
    bad = {
        "scoring": {"max_raw": 90, "bands": {"medium": 30, "high": 60}},
        "rules": [
            {
                "id": "r1",
                "weight": 10,
                "confidence": 1.5,  # out of range (0..1)
                "when": {"type": "format_on_web", "params": {}},
            }
        ],
    }
    with _client(tmp_path, config_dir=tmp_path / "config") as client:
        assert client.put("/api/config/rules", json=bad).status_code == 422
