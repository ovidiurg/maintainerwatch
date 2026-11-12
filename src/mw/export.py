from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from . import db
from .config import Config

PRIORITY = ["system", "name", "score", "band", "model_version", "inputs_hash",
            "computed_at", "downloads_weekly", "osv_count", "repo_url", "license"]


def _records(cfg: Config) -> list[dict]:
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = conn.execute(
        """SELECT s.system, s.name, s.score, s.band, s.model_version,
                  s.inputs_hash, s.computed_at,
                  p.downloads_weekly, p.osv_count, p.repo_url, p.license
           FROM scores s
           LEFT JOIN packages p ON p.system = s.system AND p.name = s.name
           ORDER BY s.score DESC, s.name ASC"""
    ).fetchall()
    signal_rows = conn.execute(
        "SELECT system, name, signal_type, value FROM signals"
    ).fetchall()
    conn.close()

    signal_map: dict[tuple[str, str], dict[str, float]] = {}
    for r in signal_rows:
        signal_map.setdefault((r["system"], r["name"]), {})[r["signal_type"]] = r["value"]

    records = []
    for r in rows:
        rec = {k: r[k] for k in r.keys()}
        for sig_name, value in signal_map.get((r["system"], r["name"]), {}).items():
            rec[f"sig_{sig_name}"] = value
        records.append(rec)
    return records


def export_dataset(cfg: Config, fmt: str = "parquet") -> tuple[Path, int]:
    records = _records(cfg)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    if fmt == "parquet":
        import polars as pl

        path = cfg.data_dir / f"maintainerwatch-{stamp}.parquet"
        pl.DataFrame(records).write_parquet(path)
        return path, len(records)

    if fmt == "csv":
        path = cfg.data_dir / f"maintainerwatch-{stamp}.csv"
        keys: list[str] = list(PRIORITY)
        for rec in records:
            for k in rec:
                if k not in keys:
                    keys.append(k)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return path, len(records)

    raise ValueError(f"unsupported export format: {fmt}")


def export_json(cfg: Config) -> str:
    return json.dumps(_records(cfg), indent=2, default=str)
