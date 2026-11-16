from __future__ import annotations

from mw import db, pipeline
from mw.config import load_config
from mw.models import Package


def _cfg(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "alerts.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.record_score(conn, "npm", "pkg", 60.0, "high", cfg.model_version, "h", "2026-01-01")
    db.record_signal(
        conn, "npm", "pkg", "publisher_change", 0.0, "low", "{}",
        cfg.model_version, "2026-01-01",
    )
    db.record_signal(
        conn, "npm", "pkg", "publisher_change", 1.0, "high", "{}",
        "0.0.1", "2026-01-01",
    )
    conn.commit()
    conn.close()
    return cfg


def test_signal_filter_ignores_other_model_versions(tmp_path):
    cfg = _cfg(tmp_path)
    assert pipeline.alerts(
        cfg, min_score=50, signal="publisher_change", min_signal=0.5
    ) == []


def test_min_signal_without_named_signal_requires_any_current_signal(tmp_path):
    cfg = _cfg(tmp_path)
    # The old-model signal is high, but the current signal is low.
    assert pipeline.alerts(cfg, min_score=50, min_signal=0.5) == []
    conn = db.connect(cfg.db_path)
    db.record_signal(
        conn, "npm", "pkg", "typosquat", 0.6, "medium", "{}",
        cfg.model_version, "2026-01-01",
    )
    conn.commit()
    conn.close()
    result = pipeline.alerts(cfg, min_score=50, min_signal=0.5)
    assert [item["name"] for item in result] == ["pkg"]
