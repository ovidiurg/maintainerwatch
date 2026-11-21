from __future__ import annotations

from fastapi.testclient import TestClient

from mw import db, history
from mw.api import create_app
from mw.config import load_config
from mw.models import Package, Version


def _setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "history.sqlite"
    cfg.data_dir = tmp_path
    cfg.api.rate_limit_rpm = 0
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.upsert_versions(conn, [
        Version(system="npm", name="pkg", version="1.0.0", published_at="2025-01-01T00:00:00Z", publisher_email="old@example.com"),
        Version(system="npm", name="pkg", version="1.1.0", published_at="2026-01-01T00:00:00Z", publisher_email="new@example.com"),
    ])
    db.record_snapshot(conn, "npm", "pkg", "2025-01-01T00:00:00Z", '["old@example.com"]', "h1")
    db.record_snapshot(conn, "npm", "pkg", "2026-01-01T00:00:00Z", '["new@example.com"]', "h2")
    conn.commit()
    conn.close()
    return cfg


def test_history_builder_and_api(tmp_path):
    cfg = _setup(tmp_path)
    conn = db.connect(cfg.db_path)
    result = history.build_history(conn, "npm", "pkg")
    conn.close()
    assert result is not None
    assert result["summary"]["versions"] == 2
    assert result["summary"]["publisher_changes"] == 1
    assert result["publisher_changes"][0]["from"] == "old@example.com"
    assert result["publisher_changes"][0]["to"] == "new@example.com"
    assert len(result["snapshots"]) == 2

    client = TestClient(create_app(cfg))
    response = client.get("/packages/npm/pkg/history")
    assert response.status_code == 200
    assert response.json()["summary"]["versions"] == 2
    assert client.get("/packages/npm/missing/history").status_code == 404
