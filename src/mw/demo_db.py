from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from . import db
from .config import Config

DEFAULT_QUOTAS = {
    "npm": 800,
    "pypi": 700,
    "crates": 300,
    "maven": 150,
    "github": 50,
}
COPY_TABLES = (
    "versions", "maintainers", "repo_stats", "scorecard_history", "osv",
    "signals", "scores", "snapshots", "identity_links", "dependencies",
    "dynamic_scan", "guarddog_scan", "content_scan", "package_findings",
    "package_impact", "commits",
)


def select_packages(
    conn: sqlite3.Connection,
    quotas: dict[str, int],
    model_version: str,
    include_high: bool = True,
) -> list[tuple[str, str]]:
    selected: dict[tuple[str, str], None] = {}
    for system, limit in quotas.items():
        rows = conn.execute(
            """SELECT system, name FROM packages
               WHERE system=?
               ORDER BY downloads_weekly DESC, name
               LIMIT ?""",
            (system, limit),
        ).fetchall()
        selected.update({(row["system"], row["name"]): None for row in rows})
    if include_high:
        rows = conn.execute(
            "SELECT system, name FROM scores WHERE model_version=? AND band='high'",
            (model_version,),
        ).fetchall()
        selected.update({(row["system"], row["name"]): None for row in rows})
    return sorted(selected)


def build_demo_db(
    cfg: Config,
    source: str | Path,
    out: str | Path,
    quotas: dict[str, int] | None = None,
    include_high: bool = True,
) -> dict[str, Any]:
    source = Path(source)
    out = Path(out)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.resolve() == out.resolve():
        raise ValueError("source and out must be different files")
    quotas = quotas or DEFAULT_QUOTAS
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    src = db.connect(source)
    selected = select_packages(src, quotas, cfg.model_version, include_high)
    src.close()

    dest = db.connect(out)
    db.init_db(dest)
    dest.execute("CREATE TEMP TABLE selected (system TEXT, name TEXT, PRIMARY KEY(system, name))")
    dest.executemany("INSERT INTO selected(system, name) VALUES (?, ?)", selected)
    dest.execute("ATTACH DATABASE ? AS src", (str(source),))
    dest.execute(
        """INSERT INTO packages SELECT * FROM src.packages
           WHERE EXISTS (SELECT 1 FROM selected s
                         WHERE s.system=src.packages.system AND s.name=src.packages.name)"""
    )
    for table in COPY_TABLES:
        if table in {"scores", "signals"}:
            dest.execute(
                f"""INSERT INTO {table} SELECT * FROM src.{table} t
                    WHERE t.model_version=? AND EXISTS (
                      SELECT 1 FROM selected s WHERE s.system=t.system AND s.name=t.name)""",
                (cfg.model_version,),
            )
        else:
            dest.execute(
                f"""INSERT INTO {table} SELECT * FROM src.{table} t
                    WHERE EXISTS (SELECT 1 FROM selected s
                                  WHERE s.system=t.system AND s.name=t.name)"""
            )
    dest.commit()
    dest.execute("DETACH DATABASE src")
    dest.execute("DROP TABLE selected")
    dest.commit()
    dest.execute("VACUUM")
    dest.execute("ANALYZE")
    dest.commit()
    counts = {
        table: dest.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("packages", "versions", "scores", "signals", "repo_stats", "commits")
    }
    dest.close()
    return {
        "path": str(out),
        "bytes": out.stat().st_size,
        "packages": len(selected),
        "counts": counts,
    }
