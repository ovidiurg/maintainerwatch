from __future__ import annotations

import json
from types import SimpleNamespace

from mw import db, pipeline
from mw.config import load_config
from mw.models import Package, Version


class Client:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def _setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "guarddog.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.upsert_versions(conn, [Version(
        system="npm", name="pkg", version="1.0.0",
        published_at="2024-01-01T00:00:00+00:00",
    )])
    db.record_score(conn, "npm", "pkg", 60.0, "high", cfg.model_version, "hash", "2026-01-01")
    conn.commit()
    conn.close()
    return cfg


def test_scan_guarddog_without_tool(monkeypatch):
    monkeypatch.setattr(pipeline.shutil, "which", lambda name: None)
    result = pipeline.scan_guarddog(load_config(), limit=1)
    assert result["error"] == "guarddog is not installed"


def test_scan_guarddog_pipeline(tmp_path, monkeypatch):
    cfg = _setup(tmp_path)
    monkeypatch.setattr(pipeline.shutil, "which", lambda name: "/usr/bin/guarddog")
    monkeypatch.setattr(pipeline, "make_client", lambda cfg: Client())
    monkeypatch.setattr(
        pipeline.tarball, "fetch_archive",
        lambda client, system, name, version: (b"data", "pkg.tgz"),
    )
    monkeypatch.setattr(
        pipeline.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"risk_score": "high_risk", "results": {"rule": []}}),
        ),
    )
    result = pipeline.scan_guarddog(cfg, limit=1)
    assert result == {"requested": 1, "scanned": 1, "errors": 0}
    conn = db.connect(cfg.db_path)
    row = db.get_guarddog_scan(conn, "npm", "pkg")
    assert row["risk_score"] == "high_risk"
    conn.close()
