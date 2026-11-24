from __future__ import annotations

from mw import db
from mw.config import load_config
from mw.high_band_review import build_packet, format_markdown, write_packet
from mw.models import Package


def _setup(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "review.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg", downloads_weekly=1000)])
    db.record_score(conn, "npm", "pkg", 62.0, "high", cfg.model_version, "h", "2026-01-01")
    db.record_score(conn, "npm", "other", 10.0, "low", cfg.model_version, "h2", "2026-01-01")
    db.record_signal(
        conn, "npm", "pkg", "publisher_change", 1.0, "high", "{}",
        cfg.model_version, "2026-01-01",
    )
    conn.commit()
    conn.close()
    return cfg


def test_high_band_packet_contains_only_high_and_review_fields(tmp_path):
    cfg = _setup(tmp_path)
    packet = build_packet(cfg)
    assert packet["count"] == 1
    pkg = packet["packages"][0]
    assert pkg["name"] == "pkg"
    assert pkg["top_signals"][0]["name"] == "publisher_change"
    assert pkg["review"]["status"] == "unreviewed"
    markdown = format_markdown(packet)
    assert "npm/pkg" in markdown
    assert "unreviewed" in markdown


def test_write_high_band_packet(tmp_path):
    cfg = _setup(tmp_path)
    paths = write_packet(build_packet(cfg), tmp_path / "reviews")
    assert len(paths) == 2
    assert all(path.exists() for path in paths)
