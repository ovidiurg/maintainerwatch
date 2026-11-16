from __future__ import annotations

from mw import db
from mw.models import Package


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
        "idx_signals_model",
    } <= indexes
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
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
