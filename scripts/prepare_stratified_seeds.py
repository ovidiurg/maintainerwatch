#!/usr/bin/env python3
"""Prepare a usage-stratified package sample for the MVP expansion.

Strata are download-rank bands, plus a dependency/fan-in stratum. Existing
packages and known validation positives are excluded before sampling.
"""

from __future__ import annotations

import json
import random
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds"
SEED = 20261116

PYPI_TOP = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/main/"
    "top-pypi-packages-30-days.min.json"
)
NPMS = "https://api.npms.io/v2/search?q=not:unstable&size=250&from={offset}"
CRATES = "https://crates.io/api/v1/crates?per_page=100&page={page}&sort=downloads"

STRATA = {
    "npm": [(0, 500, 400), (500, 1500, 400), (1500, 3000, 400)],
    "pypi": [(0, 500, 400), (500, 2000, 400), (2000, 10000, 400)],
    "crates": [(0, 200, 150), (200, 800, 150), (800, 2000, 150)],
}
DEPENDENCY_QUOTA = {"npm": 300, "pypi": 100, "crates": 50, "maven": 50}


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


def negative_keys() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    path = ROOT / "validation" / "v1" / "incident_packages.jsonl"
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                item = json.loads(line)
                out.add((item.get("system"), item.get("package")))
    return out


def ranked_names(system: str) -> list[str]:
    if system == "npm":
        names: list[str] = []
        seen: set[str] = set()
        offset = 0
        while len(names) < 3000:
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
        return names[:3000]
    if system == "pypi":
        doc = get_json(PYPI_TOP)
        return [
            row["project"] for row in (doc.get("rows") or [])
            if row.get("project")
        ][:10000]
    if system == "crates":
        names: list[str] = []
        page = 1
        while len(names) < 2000:
            doc = get_json(CRATES.format(page=page))
            crates = doc.get("crates") or []
            if not crates:
                break
            names.extend(crate["name"] for crate in crates if crate.get("name"))
            page += 1
        return names[:2000]
    return []


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    positives = negative_keys()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    dep_rows = conn.execute(
        """SELECT d.dep_system AS system, d.dep_name AS name, COUNT(*) AS uses
           FROM dependencies d
           LEFT JOIN packages p
             ON p.system = d.dep_system AND p.name = d.dep_name
           WHERE p.name IS NULL
           GROUP BY d.dep_system, d.dep_name
           ORDER BY uses DESC, d.dep_name"""
    ).fetchall()
    conn.close()

    for system in ("npm", "pypi", "crates"):
        known = existing(system)
        ranked = ranked_names(system)
        selected: list[str] = []
        used: set[str] = set()
        for start, end, quota in STRATA[system]:
            pool = [
                name for name in ranked[start:end]
                if name not in known and name not in used
                and (system, name) not in positives
            ]
            rng = random.Random(f"{SEED}:{system}:{start}")
            take = min(quota, len(pool))
            selected.extend(rng.sample(pool, take) if take else [])
            used.update(selected[-take:])
        # Dependency stratum, then fill any remaining quota from ranked head.
        deps = [
            row["name"] for row in dep_rows
            if row["system"] == system and row["name"] not in known
            and row["name"] not in used
            and (system, row["name"]) not in positives
        ]
        rng = random.Random(f"{SEED}:{system}:deps")
        take = min(DEPENDENCY_QUOTA.get(system, 0), len(deps))
        selected.extend(rng.sample(deps, take) if take else [])
        used.update(selected[-take:])
        selected = list(dict.fromkeys(selected))
        path = OUT / f"stratified-{system}.txt"
        path.write_text("\n".join(selected) + ("\n" if selected else ""), encoding="utf-8")
        print(f"{system}: {len(selected)} stratified seeds -> {path}")


if __name__ == "__main__":
    main()
