#!/usr/bin/env python3
"""Write missing high-usage npm packages from the npms.io ranking."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds" / "npm-priority.txt"
TARGET = 8000
NPMS = "https://api.npms.io/v2/search?q=not:unstable&size=250&from={offset}"


def main() -> None:
    names: list[str] = []
    seen: set[str] = set()
    offset = 0
    while len(names) < TARGET:
        request = urllib.request.Request(
            NPMS.format(offset=offset), headers={"User-Agent": "MaintainerWatch/0.5.1"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            doc = json.load(response)
        results = doc.get("results") or []
        if not results:
            break
        for item in results:
            name = (item.get("package") or {}).get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        offset += 250
    conn = sqlite3.connect(DB)
    existing = {row[0] for row in conn.execute("SELECT name FROM packages WHERE system='npm'")}
    conn.close()
    missing = [name for name in names if name not in existing]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"top {len(names)} npm by ranking; {len(missing)} missing -> {OUT}")


if __name__ == "__main__":
    main()
