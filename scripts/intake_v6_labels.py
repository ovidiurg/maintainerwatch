#!/usr/bin/env python3
"""Download fresh OSV MAL data and write current-state v6 label candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OSV = "https://osv-vulnerabilities.storage.googleapis.com"
PREVIOUS = (
    "validation/v1", "validation/v3", "validation/v4", "validation/v5",
    "validation/historical",
)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
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


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "MaintainerWatch/v6-intake"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)


def latest_versions(db: Path) -> dict[tuple[str, str], str]:
    conn = sqlite3.connect(db)
    latest: dict[tuple[str, str], tuple[str, str]] = {}
    for system, name, version, published in conn.execute(
        "SELECT system, name, version, published_at FROM versions"
    ):
        key = (system, name)
        if key not in latest or (published or "") > latest[key][1]:
            latest[key] = (version, published or "")
    conn.close()
    return {key: value[0] for key, value in latest.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="validation/v6/snapshot.json")
    parser.add_argument("--db", default=None)
    parser.add_argument("--out", default="data/validation-v6/new-osv-labels.jsonl")
    parser.add_argument("--cache-dir", default="data/validation-v6/osv-cache")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--npm-zip", default=None)
    parser.add_argument("--pypi-zip", default=None)
    parser.add_argument("--since", default=None, help="Minimum published date, default snapshot_at")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    since = args.since or snapshot["snapshot_at"]
    db = Path(args.db or snapshot["snapshot_db"])
    cache = Path(args.cache_dir)
    zips = {
        "npm": Path(args.npm_zip) if args.npm_zip else cache / "npm-all.zip",
        "PyPI": Path(args.pypi_zip) if args.pypi_zip else cache / "pypi-all.zip",
    }
    for ecosystem, path in zips.items():
        if args.refresh or not path.exists():
            download(f"{OSV}/{ecosystem}/all.zip", path)

    latest = latest_versions(db)
    previous = prior_keys()
    selected: list[dict] = []
    for ecosystem, path in zips.items():
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not Path(name).name.startswith("MAL-") or not name.endswith(".json"):
                    continue
                try:
                    record = json.loads(archive.read(name))
                except (KeyError, json.JSONDecodeError):
                    continue
                if (record.get("published") or "") < since:
                    continue
                for affected in record.get("affected") or []:
                    package = (affected.get("package") or {}).get("name")
                    system = "npm" if ecosystem == "npm" else "pypi"
                    key = (system, package)
                    if not package or key in previous or key not in latest:
                        continue
                    if latest[key] in (affected.get("versions") or []):
                        selected.append(record)
                        break
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in selected) + ("\n" if selected else ""),
        encoding="utf-8",
    )
    print(json.dumps({
        "since": since,
        "new_current_state_labels": len(selected),
        "out": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
