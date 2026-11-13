from __future__ import annotations

from fastapi.testclient import TestClient

from mw import db
from mw.api import create_app
from mw.config import AlertRule, load_config
from mw.models import Package


def _setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "test.sqlite"
    cfg.data_dir = tmp_path
    cfg.alerts.rules = [AlertRule(name="high", min_score=40)]
    cfg.api.rate_limit_rpm = 0

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(
        conn,
        [
            Package(system="npm", name="a", downloads_weekly=1),
            Package(system="npm", name="b", downloads_weekly=2),
        ],
    )
    db.record_score(conn, "npm", "a", 60.0, "high", cfg.model_version, "hash-a", "2026-01-01")
    db.record_score(conn, "npm", "b", 20.0, "low", cfg.model_version, "hash-b", "2026-01-01")
    db.record_signal(conn, "npm", "a", "publisher_change", 1.0, "high", "{}", cfg.model_version, "2026-01-01")
    db.record_signal(conn, "npm", "b", "publisher_change", 0.0, "low", "{}", cfg.model_version, "2026-01-01")
    conn.commit()
    conn.close()
    return cfg


def test_packages_pagination(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))

    first = client.get("/packages?limit=1&offset=0")
    assert first.status_code == 200
    assert len(first.json()) == 1
    assert first.json()[0]["name"] == "a"
    assert first.headers["X-Total-Count"] == "2"
    assert first.headers["X-Next-Offset"] == "1"

    second = client.get("/packages?limit=1&offset=1")
    assert second.status_code == 200
    assert second.json()[0]["name"] == "b"
    assert second.headers["X-Next-Offset"] == ""


def test_package_detail_and_health(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    detail = client.get("/packages/npm/a")
    assert detail.status_code == 200
    assert detail.json()["name"] == "a"
    assert detail.json()["score"] == 60.0

    missing = client.get("/packages/npm/missing")
    assert missing.status_code == 404


def test_alert_rules(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))
    response = client.get("/alert-rules")
    assert response.status_code == 200
    rules = response.json()
    assert rules[0]["rule"] == "high"
    assert rules[0]["count"] == 1


def test_api_key(tmp_path, monkeypatch):
    cfg = _setup(tmp_path)
    cfg.api.api_key_env = "MW_TEST_API_KEY"  # pragma: allowlist secret
    monkeypatch.setenv("MW_TEST_API_KEY", "secret")  # pragma: allowlist secret
    client = TestClient(create_app(cfg))

    assert client.get("/health").status_code == 200
    assert client.get("/packages").status_code == 401
    assert client.get("/packages", headers={"X-API-Key": "secret"}).status_code == 200


def test_rate_limit(tmp_path):
    cfg = _setup(tmp_path)
    cfg.api.rate_limit_rpm = 1
    client = TestClient(create_app(cfg))

    assert client.get("/systems").status_code == 200
    assert client.get("/systems").status_code == 429


def test_openapi_and_docs(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))
    assert client.get("/openapi.json").status_code == 200
    assert "/packages" in client.get("/openapi.json").json()["paths"]
    assert client.get("/docs").status_code == 200
