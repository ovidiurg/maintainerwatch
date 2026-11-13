#!/usr/bin/env python3
"""Prepare seed files for a case-control validation ingest.

Writes data/validation/seeds/{system}.txt with recent positive packages plus
matched benign controls. Run the ingest with config/validation.yaml.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "validation" / "v1"
OUT = ROOT / "data" / "validation" / "seeds"

POSITIVES_PER_SYSTEM = 120
CONTROLS_PER_SYSTEM = 120


def load(name: str) -> list[dict]:
    path = DATA / name
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    incidents = {item["incident_id"]: item for item in load("incidents.jsonl")}
    packages = load("incident_packages.jsonl")
    controls = load("controls.jsonl")

    positives: dict[str, dict[str, dict]] = defaultdict(dict)
    for package in packages:
        system = package.get("system")
        if system not in {"npm", "pypi"}:
            continue
        incident = incidents.get(package.get("incident_id"), {})
        if incident.get("priority") != "high":
            continue
        name = package.get("package")
        if not name:
            continue
        record = {
            "package": name,
            "incident_id": package.get("incident_id"),
            "attack_type": incident.get("attack_type"),
            "disclosure_date": incident.get("disclosure_date"),
        }
        existing = positives[system].get(name)
        if existing is None or (record["disclosure_date"] or "") > (existing["disclosure_date"] or ""):
            positives[system][name] = record

    controls_by_system: dict[str, dict[str, dict]] = defaultdict(dict)
    for control in controls:
        system = control.get("system")
        if system not in {"npm", "pypi"}:
            continue
        controls_by_system[system][control["package"]] = control

    OUT.mkdir(parents=True, exist_ok=True)
    for system in ("npm", "pypi"):
        positive_items = sorted(
            positives[system].values(),
            key=lambda item: item.get("disclosure_date") or "",
            reverse=True,
        )[:POSITIVES_PER_SYSTEM]
        control_items = list(controls_by_system[system].values())[:CONTROLS_PER_SYSTEM]
        names = [item["package"] for item in positive_items]
        names.extend(item["package"] for item in control_items)
        names = list(dict.fromkeys(names))
        path = OUT / f"{system}.txt"
        path.write_text("\n".join(names) + "\n", encoding="utf-8")
        print(
            f"{system}: {len(positive_items)} positives, "
            f"{len(control_items)} controls, {len(names)} unique seeds -> {path}"
        )


if __name__ == "__main__":
    main()
