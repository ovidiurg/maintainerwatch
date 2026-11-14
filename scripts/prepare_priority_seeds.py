#!/usr/bin/env python3
"""Write missing high-usage package seeds for a priority ingest."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds"

PYPI_TOP = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/main/"
    "top-pypi-packages-30-days.min.json"
)
NPMS = "https://api.npms.io/v2/search?q=not:unstable&size=250&from={offset}"
CRATES = "https://crates.io/api/v1/crates?per_page=100&page={page}&sort=downloads"


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "MaintainerWatch/0.4"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def existing(system: str) -> set[str]:
    conn = sqlite3.connect(DB)
    names = {row[0] for row in conn.execute(
        "SELECT name FROM packages WHERE system=?", (system,)
    )}
    conn.close()
    return names


def npm_names(limit: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    offset = 0
    while len(names) < limit:
        doc = get_json(NPMS.format(offset=offset))
        results = doc.get("results") or []
        if not results:
            break
        for item in results:
            name = (item.get("package") or {}).get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        offset += 250
    return names[:limit]


def pypi_names(limit: int) -> list[str]:
    doc = get_json(PYPI_TOP)
    return [row["project"] for row in (doc.get("rows") or []) if row.get("project")][:limit]


def crates_names(limit: int) -> list[str]:
    names: list[str] = []
    page = 1
    while len(names) < limit:
        doc = get_json(CRATES.format(page=page))
        crates = doc.get("crates") or []
        if not crates:
            break
        names.extend(crate["name"] for crate in crates if crate.get("name"))
        page += 1
    return names[:limit]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for system, limit, fetcher in (
        ("npm", 3000, npm_names),
        ("pypi", 3000, pypi_names),
        ("crates", 1000, crates_names),
    ):
        known = existing(system)
        names = [name for name in fetcher(limit) if name not in known]
        path = OUT / f"priority-{system}.txt"
        path.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
        print(f"{system}: {len(names)} missing priority packages -> {path}")


if __name__ == "__main__":
    main()
