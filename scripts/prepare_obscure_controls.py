#!/usr/bin/env python3
"""Prepare a sample of legitimate-looking, low-adoption packages.

Candidates are transitive dependencies already observed in the main database
but not ingested as top-level packages. They are dependencies of popular
packages, so they are plausibly legitimate; their adoption is measured during
ingest so the evaluation can keep only obscure ones.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
POSITIVES = ROOT / "validation" / "v1" / "incident_packages.jsonl"
OUT = ROOT / "data" / "validation-obscure" / "seeds"
NPM_LIMIT = 150


def positive_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if not POSITIVES.exists():
        return keys
    with POSITIVES.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            keys.add((item.get("system"), item.get("package")))
    return keys


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    positives = positive_keys()
    OUT.mkdir(parents=True, exist_ok=True)

    for system, limit in (("npm", NPM_LIMIT), ("pypi", None)):
        rows = conn.execute(
            """SELECT d.dep_name AS name, COUNT(*) AS uses
               FROM dependencies d
               LEFT JOIN packages p
                 ON p.system = d.dep_system AND p.name = d.dep_name
               WHERE d.dep_system = ? AND p.name IS NULL
               GROUP BY d.dep_name
               ORDER BY uses ASC, d.dep_name ASC""",
            (system,),
        ).fetchall()
        names = [
            row["name"] for row in rows
            if (system, row["name"]) not in positives
        ]
        if limit is not None:
            names = names[:limit]
        path = OUT / f"{system}.txt"
        path.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
        print(f"{system}: {len(names)} candidate controls -> {path}")

    conn.close()


if __name__ == "__main__":
    main()
