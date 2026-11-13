from __future__ import annotations

from mw import db, pipeline
from mw.config import load_config
from mw.models import Package


class DummyClient:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_backfill_limit_keeps_unprocessed_dependencies(tmp_path, monkeypatch):
    cfg = load_config()
    cfg.db_path = tmp_path / "db.sqlite"
    cfg.data_dir = tmp_path

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    for name in ("a", "b", "c"):
        db.upsert_packages(conn, [Package(system="npm", name=name)])
    db.upsert_dependencies(conn, [
        ("npm", "a", "1.0", "npm", "b"),
        ("npm", "b", "1.0", "npm", "c"),
        ("npm", "c", "1.0", "npm", "d"),
    ])
    conn.commit()
    conn.close()

    monkeypatch.setattr(pipeline, "make_client", lambda cfg: DummyClient())
    monkeypatch.setattr(
        pipeline.npm, "fetch_dependencies", lambda client, name: []
    )

    pipeline.backfill_dependencies(cfg, system="npm", limit=2)

    conn = db.connect(cfg.db_path)
    remaining = {
        (row["name"], row["dep_name"])
        for row in conn.execute(
            "SELECT name, dep_name FROM dependencies WHERE system='npm'"
        )
    }
    conn.close()
    assert ("c", "d") in remaining
    assert ("a", "b") not in remaining
    assert ("b", "c") not in remaining
