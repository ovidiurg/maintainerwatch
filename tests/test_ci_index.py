from __future__ import annotations

import json

from mw import db
from mw.ci_index import build_index, write_index
from mw.config import load_config
from mw.models import Package


def test_build_compact_index(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "index.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.record_score(conn, "npm", "pkg", 62.0, "high", cfg.model_version, "h", "2026-01-01")
    db.record_signal(
        conn, "npm", "pkg", "publisher_change", 1.0, "high", "{}",
        cfg.model_version, "2026-01-01",
    )
    conn.commit()
    index = build_index(conn, cfg)
    assert index["model_version"] == cfg.model_version
    assert index["counts"]["packages"] == 1
    assert index["packages"]["npm:pkg"]["band"] == "high"
    assert index["packages"]["npm:pkg"]["confidence"] == "high"
    path, count = write_index(conn, cfg, tmp_path / "index.json")
    assert count == 1
    assert json.loads(path.read_text())["packages"]["npm:pkg"]["score"] == 62.0
    assert path.with_suffix(".json.sha256").exists()
    conn.close()
