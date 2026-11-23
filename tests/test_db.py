from __future__ import annotations

from mw import db
from mw.models import Package, Version


def test_init_db_creates_performance_indexes_and_pragmas(tmp_path):
    conn = db.connect(tmp_path / "maintainerwatch.sqlite")
    db.init_db(conn)
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    assert {
        "idx_deps_dep_lower",
        "idx_maintainers_identity_lower",
        "idx_osv_vuln",
        "idx_packages_name_lower",
        "idx_packages_top",
        "idx_scores_model_score",
        "idx_scores_model_band_score",
        "idx_scores_model_system_score",
        "idx_signals_model",
    } <= indexes
    assert {
        "idx_signals_pkg",
        "idx_scores_pkg",
        "idx_maintainers_identity",
        "idx_versions_publisher_email",
        "idx_versions_publisher_name",
    }.isdisjoint(indexes)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()


def test_version_order_uses_published_at_with_nulls_first(tmp_path):
    conn = db.connect(tmp_path / "versions.sqlite")
    db.init_db(conn)
    db.upsert_versions(conn, [
        Version(system="npm", name="pkg", version="1.0.0", published_at="2025-01-01"),
        Version(system="npm", name="pkg", version="0.9.0", published_at=None),
        Version(system="npm", name="pkg", version="1.1.0", published_at="2024-01-01"),
    ])
    versions = db.get_versions(conn, "npm", "pkg")
    assert [row["version"] for row in versions] == ["0.9.0", "1.1.0", "1.0.0"]
    conn.close()


def test_scores_filter_indexes_are_used():
    conn = db.connect(":memory:")
    db.init_db(conn)
    band_plan = [row[3] for row in conn.execute(
        """EXPLAIN QUERY PLAN
           SELECT system, name, score, band FROM scores
           WHERE model_version=? AND band=?
           ORDER BY score DESC, name LIMIT 10""",
        ("0.5.3", "high"),
    )]
    system_plan = [row[3] for row in conn.execute(
        """EXPLAIN QUERY PLAN
           SELECT system, name, score, band FROM scores
           WHERE model_version=? AND system=?
           ORDER BY score DESC, name LIMIT 10""",
        ("0.5.3", "npm"),
    )]
    assert any("idx_scores_model_band_score" in item for item in band_plan)
    assert any("idx_scores_model_system_score" in item for item in system_plan)
    conn.close()


def test_init_db_drops_legacy_indexes(tmp_path):
    conn = db.connect(tmp_path / "legacy.sqlite")
    db.init_db(conn)
    conn.execute("CREATE INDEX idx_signals_pkg ON signals (system, name)")
    conn.commit()
    db.init_db(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_signals_pkg" not in names
    conn.close()


def test_bulk_upsert_commit_flag_can_be_deferred():
    conn = db.connect(":memory:")
    db.init_db(conn)
    db.upsert_packages(
        conn, [Package(system="npm", name="pkg")], commit=False
    )
    assert conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 1
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 0
    conn.close()


def test_scorecard_history_table_and_index(tmp_path):
    conn = db.connect(tmp_path / "scorecard-history.sqlite")
    db.init_db(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_scorecard_history_pkg" in names
    conn.execute(
        "INSERT INTO repo_stats (system,name,repo_url) VALUES (?,?,?)",
        ("npm", "pkg", None),
    )
    conn.commit()
    db.update_repo_scorecard(conn, "npm", "pkg", 5.0, "[]")
    rows = conn.execute(
        "SELECT score FROM scorecard_history WHERE system=? AND name=?",
        ("npm", "pkg"),
    ).fetchall()
    assert [row[0] for row in rows] == [5.0]
    conn.close()
