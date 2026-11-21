#!/usr/bin/env python3
"""Build a frozen current-state validation holdout from a snapshot and labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = (
    "validation/v1", "validation/v3", "validation/v4", "validation/v5",
    "validation/historical",
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prior_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for directory in PREVIOUS:
        for name in ("incident_packages.jsonl", "controls.jsonl"):
            path = ROOT / directory / name
            if path.exists():
                keys.update(
                    (row.get("system"), row.get("package"))
                    for row in load_jsonl(path)
                    if row.get("package")
                )
    return keys


def latest_versions(conn: sqlite3.Connection) -> dict[tuple[str, str], str]:
    latest: dict[tuple[str, str], tuple[str, str]] = {}
    for system, name, version, published in conn.execute(
        "SELECT system, name, version, published_at FROM versions"
    ):
        key = (system, name)
        if key not in latest or (published or "") > latest[key][1]:
            latest[key] = (version, published or "")
    return {key: value[0] for key, value in latest.items()}


def download_band(value: int) -> str:
    if value >= 1_000_000:
        return "high"
    if value >= 100_000:
        return "medium"
    if value >= 10_000:
        return "low"
    if value >= 1_000:
        return "very_low"
    return "tail"


def extract_labels(rows: list[dict], latest: dict[tuple[str, str], str]) -> list[dict]:
    selected: dict[tuple[str, str], dict] = {}
    for row in rows:
        record_id = row.get("id") or row.get("incident_id")
        published = row.get("published") or row.get("disclosure_date") or ""
        ecosystem = row.get("ecosystem")
        affected = row.get("affected") or []
        if ecosystem not in {"npm", "PyPI"}:
            continue
        system = "npm" if ecosystem == "npm" else "pypi"
        for item in affected:
            package = (item.get("package") or {}).get("name") if "package" in item else item.get("name")
            versions = set(item.get("versions") or [])
            key = (system, package)
            if not package or key not in latest or latest[key] not in versions:
                continue
            candidate = {
                "incident_id": f"holdout-{record_id}-{package}",
                "title": f"Holdout {record_id}: {package}",
                "ecosystem": system,
                "systems": [system],
                "attack_type": "malicious_package",
                "summary": f"Fresh current-state holdout label {record_id}.",
                "observation_cutoff": published,
                "cutoff_basis": "holdout_snapshot",
                "source_urls": [f"https://osv.dev/vulnerability/{record_id}"],
                "source_types": ["osv_mal"],
                "source_licenses": ["Apache-2.0"],
                "confidence": "high",
                "priority": "high",
                "schema_version": "1.0",
                "dataset_version": "v6",
                "package": package,
                "affected_versions": sorted(versions),
            }
            existing = selected.get(key)
            if existing is None or published > existing["observation_cutoff"]:
                selected[key] = candidate
    return list(selected.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-db", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", default="validation/v6")
    parser.add_argument("--data-dir", default="data/validation-v6")
    parser.add_argument("--controls-per-positive", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261121)
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise SystemExit(f"labels not found: {labels_path}")
    labels = extract_labels(load_jsonl(labels_path), latest_versions(sqlite3.connect(args.snapshot_db)))
    labels = [row for row in labels if (row["ecosystem"], row["package"]) not in prior_keys()]
    if len(labels) < 50:
        raise SystemExit(
            f"refusing to freeze a holdout with {len(labels)} positives; need at least 50"
        )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    frozen_db = data_dir / "maintainerwatch.sqlite"
    shutil.copy2(args.snapshot_db, frozen_db)

    conn = sqlite3.connect(frozen_db)
    conn.row_factory = sqlite3.Row
    positives = {(row["ecosystem"], row["package"]) for row in labels}
    previous = prior_keys()
    pools: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in conn.execute("SELECT system, name, downloads_weekly FROM packages"):
        key = (row["system"], row["name"])
        if key in positives or key in previous:
            continue
        pools[(row["system"], download_band(int(row["downloads_weekly"] or 0)))].append(row["name"])
    rng = random.Random(args.seed)
    controls = []
    used_controls: set[str] = set()
    for row in labels:
        system = row["ecosystem"]
        band = download_band(int(conn.execute(
            "SELECT downloads_weekly FROM packages WHERE system=? AND name=?",
            (system, row["package"]),
        ).fetchone()[0] or 0))
        eligible = pools.get((system, band), [])
        rng.shuffle(eligible)
        added = 0
        for package in eligible:
            key = f"{system}:{package.lower()}"
            if key in used_controls:
                continue
            used_controls.add(key)
            controls.append({
                "control_id": f"holdout-control-{system}-{package.lower()}",
                "system": system,
                "package": package,
                "as_of": row["observation_cutoff"],
                "label": "benign",
                "matched_incident_id": row["incident_id"],
                "match_features": {"download_band": band},
                "source": "maintainerwatch-db",
                "exclusion_checks": {"prior_holdout_overlap": True, "positive_overlap": True},
                "split": "test",
                "schema_version": "1.0",
                "dataset_version": "v6",
            })
            added += 1
            if added >= args.controls_per_positive:
                break
    conn.close()

    incidents = []
    packages = []
    for row in labels:
        incident = {key: row[key] for key in (
            "incident_id", "title", "ecosystem", "systems", "attack_type",
            "summary", "observation_cutoff", "cutoff_basis", "source_urls",
            "source_types", "source_licenses", "confidence", "priority",
            "schema_version", "dataset_version",
        )}
        incidents.append(incident)
        packages.append({
            "incident_id": row["incident_id"],
            "system": row["ecosystem"],
            "package": row["package"],
            "affected_versions": row["affected_versions"],
            "label": "malicious_package",
            "label_confidence": "high",
            "source": "osv",
            "source_urls": row["source_urls"],
            "schema_version": "1.0",
            "dataset_version": "v6",
        })
    (out / "incidents.jsonl").write_text("\n".join(json.dumps(x, sort_keys=True) for x in incidents) + "\n", encoding="utf-8")
    (out / "incident_packages.jsonl").write_text("\n".join(json.dumps(x, sort_keys=True) for x in packages) + "\n", encoding="utf-8")
    (out / "controls.jsonl").write_text("\n".join(json.dumps(x, sort_keys=True) for x in controls) + "\n", encoding="utf-8")
    (out / "protocol.json").write_text(json.dumps({
        "dataset_version": "v6",
        "status": "frozen",
        "snapshot_db": str(frozen_db),
        "snapshot_sha256": hashlib.sha256(frozen_db.read_bytes()).hexdigest(),
        "labels": len(incidents),
        "controls": len(controls),
        "primary_metrics": ["auc", "average_precision", "threshold_40"],
        "guardrails": ["no leakage from v1-v5", "no osv_risk-only evaluation", "single candidate"],
        "frozen": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"positives": len(incidents), "controls": len(controls), "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
