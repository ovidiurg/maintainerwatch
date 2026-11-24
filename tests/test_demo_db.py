from __future__ import annotations

from mw import db
from mw.config import load_config
from mw.demo_db import build_demo_db
from mw.models import Package, Version


def test_demo_db_copies_selected_packages_and_high(tmp_path):
    cfg = load_config()
    cfg.db_path = tmp_path / "source.sqlite"
    cfg.data_dir = tmp_path
    src = db.connect(cfg.db_path)
    db.init_db(src)
    db.upsert_packages(src, [
        Package(system="npm", name="popular", downloads_weekly=1000),
        Package(system="npm", name="less-popular", downloads_weekly=10),
        Package(system="pypi", name="py-popular", downloads_weekly=500),
    ])
    db.upsert_versions(src, [
        Version(system="npm", name="popular", version="1.0.0", published_at="2026-01-01"),
        Version(system="npm", name="less-popular", version="1.0.0", published_at="2026-01-01"),
        Version(system="pypi", name="py-popular", version="1.0.0", published_at="2026-01-01"),
    ])
    db.record_score(src, "npm", "less-popular", 60.0, "high", cfg.model_version, "h", "2026-01-01")
    db.record_score(src, "npm", "popular", 10.0, "low", cfg.model_version, "h2", "2026-01-01")
    db.record_score(src, "pypi", "py-popular", 10.0, "low", cfg.model_version, "h3", "2026-01-01")
    db.record_signal(
        src, "npm", "popular", "publisher_change", 0.5, "medium", "{}",
        cfg.model_version, "2026-01-01",
    )
    src.commit()
    src.close()

    result = build_demo_db(cfg, cfg.db_path, tmp_path / "demo.sqlite", {"npm": 1, "pypi": 1})
    assert result["packages"] == 3
    dest = db.connect(result["path"])
    names = {row["name"] for row in dest.execute("SELECT name FROM packages")}
    assert names == {"popular", "less-popular", "py-popular"}
    assert dest.execute("SELECT COUNT(*) FROM versions").fetchone()[0] == 3
    dest.close()
