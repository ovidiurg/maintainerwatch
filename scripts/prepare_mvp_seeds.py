#!/usr/bin/env python3
"""Assemble bounded seed lists for the MVP dataset expansion."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OBSCURE = ROOT / "data" / "validation-obscure" / "seeds"
OUT = ROOT / "data" / "mvp" / "seeds"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    npm = []
    for name in ("npm.txt", "npm-random.txt"):
        path = OBSCURE / name
        if path.exists():
            npm.extend(path.read_text(encoding="utf-8").splitlines())
    pypi_path = OBSCURE / "pypi.txt"
    pypi = pypi_path.read_text(encoding="utf-8").splitlines() if pypi_path.exists() else []
    (OUT / "npm.txt").write_text("\n".join(dict.fromkeys(npm)) + "\n", encoding="utf-8")
    (OUT / "pypi.txt").write_text("\n".join(dict.fromkeys(pypi)) + "\n", encoding="utf-8")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    for system in ("crates", "maven"):
        rows = conn.execute(
            """SELECT DISTINCT d.dep_name AS name
               FROM dependencies d
               LEFT JOIN packages p
                 ON p.system = d.dep_system AND p.name = d.dep_name
               WHERE d.dep_system = ? AND p.name IS NULL
               ORDER BY d.dep_name""",
            (system,),
        ).fetchall()
        names = [row["name"] for row in rows]
        (OUT / f"{system}.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
        print(f"{system}: {len(names)} seeds")
    print(f"npm: {len(set(npm))} seeds")
    print(f"pypi: {len(set(pypi))} seeds")
    conn.close()


if __name__ == "__main__":
    main()
