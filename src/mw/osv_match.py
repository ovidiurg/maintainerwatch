from __future__ import annotations

import json
from typing import Any

from packaging.version import InvalidVersion, Version

ECOSYSTEMS = {
    "npm": "npm",
    "pypi": "PyPI",
    "crates": "crates.io",
    "maven": "Maven",
}


def _version(value: str):
    clean = str(value).strip().lstrip("vV=")
    try:
        return Version(clean)
    except InvalidVersion:
        return None


def _cmp(left: str, right: str) -> int:
    lv = _version(left)
    rv = _version(right)
    if lv is not None and rv is not None:
        return (lv > rv) - (lv < rv)
    def key(value: str):
        return tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in str(value).strip().lower().replace("-", ".").split(".")
        )
    lk, rk = key(left), key(right)
    return (lk > rk) - (lk < rk)


def _range_matches(events: list[dict], version: str) -> bool:
    start: str | None = None
    for event in events:
        if "introduced" in event:
            start = str(event["introduced"])
        elif "fixed" in event:
            fixed = str(event["fixed"])
            if start is not None and _cmp(version, start) >= 0 and _cmp(version, fixed) < 0:
                return True
            start = None
        elif "last_affected" in event:
            last = str(event["last_affected"])
            if start is not None and _cmp(version, start) >= 0 and _cmp(version, last) <= 0:
                return True
            start = None
    return start is not None and _cmp(version, start) >= 0


def affected(affected_json: str | None, system: str, name: str, version: str) -> bool:
    if not affected_json or not version:
        return False
    try:
        entries = json.loads(affected_json)
    except (TypeError, ValueError):
        return False
    ecosystem = ECOSYSTEMS.get(system)
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        package = entry.get("package") or {}
        if package.get("ecosystem") != ecosystem:
            continue
        if str(package.get("name") or "").lower() != name.lower():
            continue
        versions = entry.get("versions") or []
        if any(_cmp(version, str(item)) == 0 for item in versions):
            return True
        for range_item in entry.get("ranges") or []:
            if _range_matches(range_item.get("events") or [], version):
                return True
    return False
