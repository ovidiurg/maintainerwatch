#!/usr/bin/env python3
"""Prepare a larger case-control validation sample (validation v2)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "validation" / "v1"
OUT = ROOT / "data" / "validation-v2" / "seeds"
POSITIVES_PER_SYSTEM = 400
POSITIVES_PER_YEAR = 100
YEARS = ("2024", "2025")
CONTROLS_PER_SYSTEM = 500


def load(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    incidents = {item["incident_id"]: item for item in load("incidents.jsonl")}
    packages = load("incident_packages.jsonl")
    controls = load("controls.jsonl")
    positives: dict[str, dict[str, dict]] = defaultdict(dict)
    for package in packages:
        system = package.get("system")
        if system not in {"npm", "pypi"} or not package.get("package"):
            continue
        incident = incidents.get(package.get("incident_id"), {})
        if incident.get("priority") != "high":
            continue
        if package.get("source") == "osv":
            continue
        record = {
            "package": package["package"],
            "disclosure_date": incident.get("disclosure_date") or "",
        }
        existing = positives[system].get(package["package"])
        if existing is None or record["disclosure_date"] > existing["disclosure_date"]:
            positives[system][package["package"]] = record

    controls_by_system: dict[str, dict[str, dict]] = defaultdict(dict)
    for control in controls:
        system = control.get("system")
        if system in {"npm", "pypi"}:
            controls_by_system[system][control["package"]] = control

    OUT.mkdir(parents=True, exist_ok=True)
    for system in ("npm", "pypi"):
        by_year: dict[str, list[dict]] = defaultdict(list)
        for item in positives[system].values():
            by_year[(item.get("disclosure_date") or "")[:4]].append(item)
        positive_items = sorted(
            positives[system].values(),
            key=lambda item: item.get("disclosure_date") or "",
            reverse=True,
        )[:POSITIVES_PER_SYSTEM]
        used = {item["package"] for item in positive_items}
        for year in YEARS:
            for item in sorted(
                by_year[year], key=lambda item: item.get("disclosure_date") or "",
                reverse=True,
            ):
                if item["package"] not in used:
                    positive_items.append(item)
                    used.add(item["package"])
                if sum(1 for x in positive_items if x in by_year[year]) >= POSITIVES_PER_YEAR:
                    break
        control_items = list(controls_by_system[system].values())[:CONTROLS_PER_SYSTEM]
        names = [item["package"] for item in positive_items]
        names.extend(item["package"] for item in control_items)
        names = list(dict.fromkeys(names))
        path = OUT / f"{system}.txt"
        path.write_text("\n".join(names) + "\n", encoding="utf-8")
        print(f"{system}: {len(positive_items)} positives, {len(control_items)} controls, {len(names)} unique seeds -> {path}")


if __name__ == "__main__":
    main()
