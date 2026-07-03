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
from fastapi import HTTPException
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

        runs = client.get("/api/runs", params={"source": "demo"}).json()
        assert any(r["id"] == run_id for r in runs)

        report = client.get(f"/api/runs/{run_id}", params={"source": "demo"}).json()
        families = {f["family"] for f in report["findings"]}
        assert "Atlas Grotesk Private" in families
        assert report["summary"]["open_findings"] >= 1


def test_demo_runs_isolated_from_real(tmp_path: Path) -> None:
    # Demo scans write to reports/demo/ so "Your data" (source=real) never shows
    # them. They surface only under source=demo, and fetching needs the same source.
    with _client(tmp_path) as client:
        run_id = _run_demo_scan(client)

        assert (tmp_path / "demo" / run_id).exists()
        assert client.get("/api/runs").json() == []  # real is empty
        assert client.get(f"/api/runs/{run_id}").status_code == 404  # real lookup misses

        demo_runs = client.get("/api/runs", params={"source": "demo"}).json()
        assert any(r["id"] == run_id for r in demo_runs)
        assert client.get(f"/api/runs/{run_id}", params={"source": "demo"}).status_code == 200


def test_first_seen_after_scan(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _run_demo_scan(client)
        resp = client.get("/api/first-seen", params={"source": "demo"})
        assert resp.status_code == 200
        rows = resp.json()
        assert rows and all({"domain", "family", "first_seen"} <= set(r) for r in rows)
        assert any(r["family"] == "Atlas Grotesk Private" for r in rows)


def test_run_diff(tmp_path: Path) -> None:
    from datetime import datetime

    from fontsentry.models import Finding, RiskBand
    from fontsentry.report import json_report

    older = json_report.build_report(
        [Finding(family="Atlas", owner="X", score=80, band=RiskBand.HIGH)],
        datetime(2026, 1, 1, 0, 0, 0),
    )
    newer = json_report.build_report(
        [Finding(family="Beacon", owner="Y", score=70, band=RiskBand.HIGH)],
        datetime(2026, 2, 1, 0, 0, 0),
    )
    json_report.write_run(older, tmp_path)
    json_report.write_run(newer, tmp_path)

    with _client(tmp_path) as client:
        resp = client.get(f"/api/runs/{json_report.run_filename(newer.generated_at)}/diff")
        assert resp.status_code == 200
        d = resp.json()
        assert [f["family"] for f in d["new_findings"]] == ["Beacon"]
        assert [f["family"] for f in d["resolved_findings"]] == ["Atlas"]

        # The oldest run has nothing to compare against -> empty diff.
        oldest = client.get(f"/api/runs/{json_report.run_filename(older.generated_at)}/diff").json()
        assert oldest["new_findings"] == [] and oldest["resolved_findings"] == []


def test_known_fonts_returns_catalog_without_runs(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        fonts = client.get("/api/known-fonts").json()
        families = {f["family"] for f in fonts}
        assert "Roboto" in families  # bundled catalog is available pre-audit
        assert all(f["source"] == "catalog" for f in fonts)


def test_known_fonts_merges_detected_over_catalog(tmp_path: Path) -> None:
    from datetime import datetime

    from fontsentry.models import Finding, RiskBand
    from fontsentry.report import json_report

    rep = json_report.build_report(
        [Finding(family="Roboto", owner="Acme Type", score=50, band=RiskBand.MEDIUM)],
        datetime(2026, 1, 1, 0, 0, 0),
    )
    json_report.write_run(rep, tmp_path)  # a real run in the root

    with _client(tmp_path) as client:
        fonts = {f["family"]: f for f in client.get("/api/known-fonts").json()}
        assert fonts["Roboto"]["source"] == "detected"
        assert fonts["Roboto"]["owner"] == "Acme Type"


def test_scan_estimate_no_history(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        d = client.get("/api/scan/estimate", params={"hosts": 3, "max_pages": 10}).json()
        assert d["eta_seconds"] is None
        assert d["based_on_runs"] == 0


def test_scan_estimate_from_history(tmp_path: Path) -> None:
    from datetime import datetime

    from fontsentry.models import DomainReport
    from fontsentry.report import json_report

    rep = json_report.build_report(
        [], datetime(2026, 1, 1, 0, 0, 0), domains=[DomainReport(domain="a.com", pages_scanned=20)]
    )
    rep.duration_seconds = 10.0  # 20 pages / 10s = 2 pages/sec
    json_report.write_run(rep, tmp_path)

    with _client(tmp_path) as client:
        d = client.get("/api/scan/estimate", params={"hosts": 3, "max_pages": 10}).json()
        assert d["based_on_runs"] == 1
        assert d["eta_seconds"] == 15.0  # 3*10 planned pages / 2 pages_per_sec


def test_scan_accepts_max_pages(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        started = client.post("/api/scan", json={"mode": "demo", "max_pages_per_domain": 3})
        assert started.status_code == 200
        # invalid (0) rejected by the model
        bad = client.post("/api/scan", json={"mode": "demo", "max_pages_per_domain": 0})
        assert bad.status_code == 422


def test_export_csv(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        run_id = _run_demo_scan(client)
        resp = client.get(f"/api/runs/{run_id}/export.csv", params={"source": "demo"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers.get("content-disposition", "")
        body = resp.text
        assert body.splitlines()[0].startswith("family,family_group,owner,band,score")
        assert "Atlas Grotesk Private" in body


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


def test_origin_guard_blocks_sec_fetch_site_cross_site(tmp_path: Path) -> None:
    # Closes the null-Origin CSRF gap: browsers send Sec-Fetch-Site even when
    # Origin is absent for some requests.
    with _client(tmp_path) as client:
        blocked = client.post(
            "/api/scan", json={"mode": "demo"}, headers={"Sec-Fetch-Site": "cross-site"}
        )
        assert blocked.status_code == 403
        allowed = client.post(
            "/api/scan", json={"mode": "demo"}, headers={"Sec-Fetch-Site": "same-origin"}
        )
        assert allowed.status_code == 200


def test_scan_bad_config_marks_job_error_not_zombie(tmp_path: Path) -> None:
    # A real-mode scan against a config dir with no valid files must mark the job
    # as error, not leave it stuck "running" forever (regression for the config-
    # load-before-try bug).
    with _client(tmp_path, config_dir=tmp_path / "missing-config") as client:
        started = client.post("/api/scan", json={"mode": "real"})
        assert started.status_code == 200
        job_id = started.json()["job_id"]
        deadline = time.time() + 20
        while time.time() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "error":
                return
            assert job["status"] != "done", "scan unexpectedly succeeded with no config"
            time.sleep(0.05)
        raise AssertionError("job never reached error state — stuck running (zombie)")


def test_invalid_mode_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.post("/api/scan", json={"mode": "bogus"}).status_code == 400


def test_scan_accepts_discover_subdomains_flag(tmp_path: Path) -> None:
    # The flag is accepted; in demo mode CT lookup is skipped (real-mode only),
    # so the offline demo scan still completes normally.
    with _client(tmp_path) as client:
        started = client.post("/api/scan", json={"mode": "demo", "discover_subdomains": True})
        assert started.status_code == 200
        job_id = started.json()["job_id"]
        deadline = time.time() + 20
        while time.time() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "done":
                return
            assert job["status"] != "error", job.get("error")
            time.sleep(0.05)
        raise AssertionError("scan did not finish in time")


def test_active_jobs_lists_running_scan(tmp_path: Path) -> None:
    # A freshly-loaded UI re-attaches via GET /api/jobs. Once the scan finishes
    # the job is no longer "running", so it drops off the active list.
    with _client(tmp_path) as client:
        started = client.post("/api/scan", json={"mode": "demo"})
        job_id = started.json()["job_id"]

        active = client.get("/api/jobs").json()
        assert any(j["id"] == job_id and j["mode"] == "demo" for j in active)

        run_id = _run_demo_scan_wait(client, job_id)
        assert run_id
        assert all(j["id"] != job_id for j in client.get("/api/jobs").json())


def _run_demo_scan_wait(client: TestClient, job_id: str) -> str:
    deadline = time.time() + 20
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "done":
            return str(job["run_id"])
        assert job["status"] != "error", job.get("error")
        time.sleep(0.05)
    raise AssertionError("scan job did not finish in time")


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


def test_proof_upload_roundtrip(tmp_path: Path) -> None:
    registry_dir = tmp_path / "registry"
    with _client(tmp_path, registry_dir=registry_dir) as client:
        up = client.post(
            "/api/registry/proof",
            files={"file": ("invoice.pdf", b"%PDF-1.4 hi", "application/pdf")},
        )
        assert up.status_code == 200
        name = up.json()["name"]
        assert name == "invoice.pdf"
        assert (registry_dir / "proofs" / name).exists()

        got = client.get(f"/api/registry/proof/{name}")
        assert got.status_code == 200
        assert got.content == b"%PDF-1.4 hi"


def test_proof_upload_rejects_bad_type(tmp_path: Path) -> None:
    with _client(tmp_path, registry_dir=tmp_path / "registry") as client:
        r = client.post(
            "/api/registry/proof",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        assert r.status_code == 400


def test_proof_get_traversal_rejected(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/registry/proof/..%2f..%2fsecret").status_code in (400, 404)


def test_safe_run_path_resolve_and_contain(tmp_path: Path) -> None:
    from fontsentry.web.server import _safe_run_path

    # A legitimate report id resolves inside reports_dir.
    ok = _safe_run_path(tmp_path, "fontsentry-x.report.json")
    assert ok.parent == tmp_path.resolve()

    for bad in (
        "../secret.report.json",
        "sub/dir.report.json",
        "notareport.txt",
        "x.report.json/..",
    ):
        with pytest.raises(HTTPException):
            _safe_run_path(tmp_path, bad)


def test_proof_upload_over_cap_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fontsentry.web.server as server

    monkeypatch.setattr(server, "_MAX_PROOF_BYTES", 1024)
    with _client(tmp_path, registry_dir=tmp_path / "registry") as client:
        big = client.post(
            "/api/registry/proof",
            files={"file": ("big.pdf", b"%PDF-" + b"A" * 4096, "application/pdf")},
        )
        assert big.status_code == 413
        assert not (tmp_path / "registry" / "proofs" / "big.pdf").exists()
