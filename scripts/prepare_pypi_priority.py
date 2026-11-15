#!/usr/bin/env python3
"""Write missing high-usage PyPI packages from the top-downloads list."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds" / "pypi-priority.txt"
TARGET = 5000
TOP = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/main/"
    "top-pypi-packages-30-days.min.json"
)


def main() -> None:
    request = urllib.request.Request(TOP, headers={"User-Agent": "MaintainerWatch/0.5.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        doc = json.load(response)
    names = [
        row["project"] for row in (doc.get("rows") or [])
        if row.get("project")
    ][:TARGET]
    conn = sqlite3.connect(DB)
    existing = {row[0] for row in conn.execute("SELECT name FROM packages WHERE system='pypi'")}
    conn.close()
    missing = [name for name in names if name not in existing]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"top {len(names)} by downloads; {len(missing)} missing -> {OUT}")


if __name__ == "__main__":
    main()
