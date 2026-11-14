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
    db.upsert_impact(conn, [
        ("npm", "a", "1.0.0", 1500, 1000, 500, "deps.dev", "2026-01-01"),
        ("npm", "b", "1.0.0", 5, 3, 2, "deps.dev", "2026-01-01"),
    ])
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


def test_packages_include_impact_and_min_dependents(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))

    response = client.get("/packages?limit=10")
    assert response.status_code == 200
    assert response.json()[0]["dependent_count"] == 1500
    assert response.json()[0]["impact_tier"] == "critical"
    assert isinstance(response.json()[0]["impact_score"], float)

    filtered = client.get("/packages?min_dependents=100")
    assert filtered.headers["X-Total-Count"] == "1"
    assert [item["name"] for item in filtered.json()] == ["a"]


def test_impact_endpoint_orders_and_paginates(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))

    response = client.get("/impact?limit=1&offset=0")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "a"
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Next-Offset"] == "1"

    filtered = client.get("/impact?min_dependents=100")
    assert [item["name"] for item in filtered.json()] == ["a"]


def test_package_detail_includes_risk_and_impact(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))

    detail = client.get("/packages/npm/a")
    assert detail.status_code == 200
    body = detail.json()
    assert body["risk_type"] == "Maintainer takeover"
    assert body["risk_note"]
    assert body["next_step"]
    assert body["impact_tier"] == "critical"
    assert body["impact_score"] > 0
    assert body["context"]["dependent_count"] == 1500


def test_top_includes_impact_fields(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))
    response = client.get("/top?limit=2")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "a"
    assert "impact_score" in response.json()[0]
    assert "impact_tier" in response.json()[0]


def test_alerts_returns_matching_packages(tmp_path):
    cfg = _setup(tmp_path)
    client = TestClient(create_app(cfg))
    response = client.get("/alerts?min_score=40")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["a"]


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
    paths = client.get("/openapi.json").json()["paths"]
    assert "/packages" in paths
    assert "/impact" in paths
    assert client.get("/docs").status_code == 200
