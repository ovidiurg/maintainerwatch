#!/usr/bin/env python3
"""Write missing high-usage crates from the crates.io download ranking."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds" / "crates-priority.txt"
TARGET = 5000


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "MaintainerWatch/0.5.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    conn = sqlite3.connect(DB)
    existing = {row[0] for row in conn.execute("SELECT name FROM packages WHERE system='crates'")}
    conn.close()
    names: list[str] = []
    page = 1
    while len(names) < TARGET:
        doc = get_json(
            f"https://crates.io/api/v1/crates?per_page=100&page={page}&sort=downloads"
        )
        crates = doc.get("crates") or []
        if not crates:
            break
        names.extend(crate["name"] for crate in crates if crate.get("name"))
        page += 1
    missing = [name for name in names if name not in existing]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"top {len(names)} crates by downloads; {len(missing)} missing -> {OUT}")


if __name__ == "__main__":
    main()
