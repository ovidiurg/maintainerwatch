from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from mw import db, dynamic, pipeline
from mw.config import load_config
from mw.models import Package, Version
from worker.app import app as worker_app


def _setup(tmp_path, worker_url="http://worker:8090"):
    cfg = load_config()
    cfg.db_path = tmp_path / "dynamic.sqlite"
    cfg.data_dir = tmp_path
    cfg.dynamic.worker_url = worker_url
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


def test_dynamic_worker_requires_sandbox(monkeypatch):
    monkeypatch.delenv("DYNAMIC_SANDBOX_COMMAND", raising=False)
    client = TestClient(worker_app)
    assert client.get("/health").json()["sandbox_configured"] is False
    response = client.post("/scan", json={
        "system": "npm", "name": "pkg", "version": "1.0.0"
    })
    assert response.status_code == 503


def test_scan_dynamic_pipeline(tmp_path, monkeypatch):
    cfg = _setup(tmp_path)
    monkeypatch.setattr(dynamic, "httpx", SimpleNamespace(
        post=lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {"risk_score": "high_risk", "findings": [{"type": "network"}]},
        )
    ))
    monkeypatch.setattr(
        pipeline.dynamic, "scan_remote",
        lambda cfg, system, name, version: {
            "risk_score": "high_risk", "findings": [{"type": "network"}]
        },
    )
    result = pipeline.scan_dynamic(cfg, limit=1)
    assert result == {"requested": 1, "scanned": 1, "errors": 0}
    conn = db.connect(cfg.db_path)
    row = db.get_dynamic_scan(conn, "npm", "pkg")
    assert row["risk_score"] == "high_risk"
    conn.close()


def test_scan_remote_missing_worker():
    cfg = load_config()
    cfg.dynamic.worker_url = None
    with pytest.raises(dynamic.DynamicWorkerError):
        dynamic.scan_remote(cfg, "npm", "pkg", "1.0.0")
