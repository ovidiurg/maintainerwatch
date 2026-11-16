#!/usr/bin/env python3
"""Validate the committed validation dataset metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_INCIDENT = [
    "incident_id", "title", "ecosystem", "attack_type", "summary",
    "observation_cutoff", "cutoff_basis", "source_urls", "source_types",
    "source_licenses", "confidence", "priority", "schema_version",
    "dataset_version",
]
REQUIRED_PACKAGE = [
    "incident_id", "system", "package", "label", "label_confidence",
    "source", "schema_version", "dataset_version",
]
REQUIRED_CONTROL = [
    "control_id", "system", "package", "as_of", "label", "source",
    "schema_version", "dataset_version",
]
SYSTEMS = {"npm", "pypi", "crates", "maven", "rubygems", "go", "nuget", "packagist", "github"}


def load(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="validation/v1")
    global DATA
    DATA = ROOT / parser.parse_args().dataset
    incidents = load("incidents.jsonl")
    packages = load("incident_packages.jsonl")
    controls = load("controls.jsonl")
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))

    errors: list[str] = []
    incident_ids: set[str] = set()
    for incident in incidents:
        for field in REQUIRED_INCIDENT:
            if not incident.get(field):
                errors.append(f"incident {incident.get('incident_id')}: missing {field}")
        incident_id = incident.get("incident_id")
        if incident_id in incident_ids:
            errors.append(f"duplicate incident_id {incident_id}")
        incident_ids.add(incident_id)
        if not incident.get("systems"):
            errors.append(f"incident {incident_id}: empty systems")
        cutoff = (incident.get("observation_cutoff") or "")[:10]
        disclosure = (incident.get("disclosure_date") or "")[:10]
        if cutoff and disclosure and cutoff > disclosure:
            errors.append(f"incident {incident_id}: cutoff {cutoff} after disclosure {disclosure}")

    positive_keys: set[tuple[str, str]] = set()
    package_keys: set[tuple[str, str, str]] = set()
    for package in packages:
        for field in REQUIRED_PACKAGE:
            if not package.get(field):
                errors.append(f"package {package.get('package')}: missing {field}")
        incident_id = package.get("incident_id")
        if incident_id not in incident_ids:
            errors.append(f"package {package.get('package')}: unknown incident {incident_id}")
        system = package.get("system")
        if system not in SYSTEMS:
            errors.append(f"package {package.get('package')}: unknown system {system}")
        key = (incident_id, system, package.get("package"))
        if key in package_keys:
            errors.append(f"duplicate package {key}")
        package_keys.add(key)
        positive_keys.add((system, package.get("package")))

    control_ids: set[str] = set()
    for control in controls:
        for field in REQUIRED_CONTROL:
            if not control.get(field):
                errors.append(f"control {control.get('control_id')}: missing {field}")
        control_id = control.get("control_id")
        if control_id in control_ids:
            errors.append(f"duplicate control_id {control_id}")
        control_ids.add(control_id)
        if control.get("label") != "benign":
            errors.append(f"control {control_id}: label is not benign")
        if (control.get("system"), control.get("package")) in positive_keys:
            errors.append(f"control {control_id}: overlaps a positive package")

    counts = {
        "incidents": len(incidents),
        "incident_packages": len(packages),
        "controls": len(controls),
    }
    for key, value in counts.items():
        if manifest.get("counts", {}).get(key) != value:
            errors.append(f"manifest count {key}: {manifest.get('counts', {}).get(key)} != {value}")

    print(json.dumps({
        "counts": counts,
        "incidents_high_priority": sum(1 for i in incidents if i.get("priority") == "high"),
        "systems": sorted({p.get("system") for p in packages}),
    }, indent=2))

    if errors:
        print(f"\n{len(errors)} validation errors:", file=sys.stderr)
        for error in errors[:30]:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("validation dataset OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
