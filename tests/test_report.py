from __future__ import annotations

from mw import db
from mw.config import load_config
from mw.models import Package
from mw.report import build_report


def test_build_report_includes_risk_and_impact(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "report.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [
        Package(system="npm", name="a", downloads_weekly=10),
        Package(system="npm", name="b", downloads_weekly=1),
    ])
    db.upsert_versions(conn, [])
    db.record_score(conn, "npm", "a", 60.0, "high", cfg.model_version, "hash-a", "2026-01-01")
    db.record_score(conn, "npm", "b", 10.0, "low", cfg.model_version, "hash-b", "2026-01-01")
    db.record_signal(
        conn, "npm", "a", "publisher_change", 1.0, "high",
        '{"n_legitimate": 0}', cfg.model_version, "2026-01-01",
    )
    db.upsert_impact(conn, [
        ("npm", "a", "1.0.0", 5000, 1000, 4000, "deps.dev", "2026-01-01"),
    ])
    conn.commit()
    conn.close()

    path, count = build_report(cfg, tmp_path / "report.html")
    html = path.read_text(encoding="utf-8")
    assert count == 2
    assert "MaintainerWatch" in html
    assert "Maintainer takeover" in html
    assert "critical" in html
    assert "Confidence" in html
    assert "Coverage" in html
    assert "evidence-only" in html
    assert "high" in html
    assert "a" in html
