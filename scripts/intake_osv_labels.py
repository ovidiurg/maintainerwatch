#!/usr/bin/env python3
"""Collect candidate OSV malicious labels for human review.

Input is JSONL with one package per line:
  {"system": "npm", "name": "pkg", "version": "1.2.3", "cutoff": "2025-01-01T00:00:00Z"}

The output is a review queue, not an automatic change to validation labels.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

OSV_QUERY = "https://api.osv.dev/v1/query"
ECOSYSTEMS = {
    "npm": "npm",
    "pypi": "PyPI",
    "crates": "crates.io",
    "maven": "Maven",
}


def load_packages(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def query_package(package: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    ecosystem = ECOSYSTEMS.get(package.get("system", ""))
    if not ecosystem:
        raise ValueError(f"unsupported system: {package.get('system')}")
    body: dict[str, Any] = {"package": {"name": package["name"], "ecosystem": ecosystem}}
    if package.get("version"):
        body["version"] = package["version"]
    req = urllib.request.Request(
        OSV_QUERY,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "MaintainerWatch/0.4"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def extract_candidates(package: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for vuln in response.get("vulns", []):
        advisory_id = vuln.get("id") or ""
        if not advisory_id.startswith("MAL-"):
            continue
        out.append({
            "system": package.get("system"),
            "name": package.get("name"),
            "version": package.get("version"),
            "cutoff": package.get("cutoff"),
            "label": "malicious_package",
            "status": "candidate",
            "reviewed": False,
            "source": "osv",
            "advisory_id": advisory_id,
            "aliases": vuln.get("aliases") or [],
            "summary": vuln.get("summary") or "",
            "modified": vuln.get("modified"),
            "url": f"https://osv.dev/vulnerability/{advisory_id}",
        })
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL package queue.")
    parser.add_argument("--out", default="data/feedback/osv-labels.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    packages = load_packages(args.input)
    if args.limit:
        packages = packages[: args.limit]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple[str, str, str]] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                existing.add((
                    item.get("system", ""),
                    item.get("name", ""),
                    item.get("advisory_id", ""),
                ))

    added = 0
    errors = 0
    with out_path.open("a", encoding="utf-8") as handle:
        for package in packages:
            try:
                response = query_package(package, timeout=args.timeout)
            except (OSError, ValueError):
                errors += 1
                continue
            for item in extract_candidates(package, response):
                key = (item["system"], item["name"], item["advisory_id"])
                if key in existing:
                    continue
                handle.write(json.dumps(item, sort_keys=True) + "\n")
                existing.add(key)
                added += 1
    print(json.dumps({
        "input": args.input,
        "out": args.out,
        "packages": len(packages),
        "added": added,
        "errors": errors,
        "review_required": True,
    }, indent=2))


if __name__ == "__main__":
    main()
