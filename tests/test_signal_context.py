from __future__ import annotations

from mw import db, signal_context
from mw.config import load_config
from mw.models import Package, Version


def _setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "signal-context.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [
        Package(system="npm", name="pkg", repo_url="https://github.com/o/r", license="MIT"),
        Package(system="npm", name="other", downloads_weekly=1000),
    ])
    db.upsert_versions(conn, [
        Version(system="npm", name="pkg", version="1.0.0", published_at="2026-11-01T00:00:00Z"),
        Version(system="npm", name="pkg", version="1.1.0", published_at="2026-11-20T00:00:00Z"),
    ])
    conn.execute(
        "INSERT INTO maintainers (system,name,identity,role,source) VALUES (?,?,?,?,?)",
        ("npm", "pkg", "dev@example.com", "maintainer", "npm"),
    )
    conn.execute(
        "INSERT INTO maintainers (system,name,identity,role,source) VALUES (?,?,?,?,?)",
        ("npm", "other", "dev@example.com", "maintainer", "npm"),
    )
    conn.commit()
    return cfg, conn


def test_signal_context_blocks(tmp_path):
    cfg, conn = _setup(tmp_path)
    ctx = signal_context.build_context(conn, "npm", "pkg", {
        "typosquat": {"value": 1.0, "evidence": {"nearest": "other", "distance": 1}}
    })
    assert "publisher_change" in ctx["signal_robustness"]["dtm"]
    assert "typosquat" in ctx["signal_robustness"]["etm"]
    assert ctx["typosquat_benignity"]["checks"]["active_release"] is True
    assert ctx["typosquat_benignity"]["checks"]["overlapping_maintainers"] is True
    assert ctx["maintainer_exposure"]["other_packages"] == 1
    conn.close()


def test_scorecard_history_and_trend(tmp_path):
    cfg, conn = _setup(tmp_path)
    conn.execute(
        "INSERT INTO repo_stats (system,name,repo_url) VALUES (?,?,?)",
        ("npm", "pkg", "https://github.com/o/r"),
    )
    conn.commit()
    db.update_repo_scorecard(conn, "npm", "pkg", 5.0, "[]")
    db.update_repo_scorecard(conn, "npm", "pkg", 6.0, "[]")
    trend = db.scorecard_trend(conn, "npm", "pkg")
    assert trend["status"] == "available"
    assert trend["latest"] == 6.0
    assert trend["delta"] == 1.0
    conn.close()


def test_maintainer_exposure_query_uses_identity_index(tmp_path):
    cfg, conn = _setup(tmp_path)
    sql = """
        SELECT DISTINCT p.system, p.name, p.downloads_weekly, p.fan_in_transitive
        FROM maintainers m
        JOIN packages p ON p.system=m.system AND p.name=m.name
        WHERE LOWER(m.identity) IN (?)
          AND NOT (p.system=? AND p.name=?)
    """
    plan = [
        row[3]
        for row in conn.execute(
            "EXPLAIN QUERY PLAN " + sql,
            ("dev@example.com", "npm", "pkg"),
        )
    ]
    assert any("idx_maintainers_identity_lower" in item for item in plan)
    conn.close()
