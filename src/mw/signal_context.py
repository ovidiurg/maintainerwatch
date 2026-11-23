from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

DTM_SIGNALS = {
    "publisher_change",
    "maintainer_continuity",
    "account_age",
    "signing_gap",
    "commit_anomaly",
    "osv_risk",
    "depsdev_findings",
    "scorecard",
    "dependency_risk",
    "release_anomaly",
}
ETM_SIGNALS = {
    "bus_factor",
    "typosquat",
    "license_inconsistency",
    "install_script",
}
ROBUSTNESS = {
    "dtm": sorted(DTM_SIGNALS),
    "etm": sorted(ETM_SIGNALS),
    "note": "DTM = history/third-party/restricted-control evidence; ETM = metadata or content that a package publisher can more easily manipulate.",
}


def _recent_days(value: str | None, reference: datetime) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (reference - parsed).days


def typosquat_benignity(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    signal: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence = (signal or {}).get("evidence") or {}
    if not evidence or (signal or {}).get("value", 0.0) <= 0:
        return {"status": "not_applicable"}
    reference = datetime.now(timezone.utc)
    package = conn.execute(
        "SELECT repo_url, license FROM packages WHERE system=? AND name=?",
        (system, name),
    ).fetchone()
    versions = conn.execute(
        "SELECT published_at FROM versions WHERE system=? AND name=?",
        (system, name),
    ).fetchall()
    latest_gap = min(
        (
            value
            for row in versions
            if (value := _recent_days(row["published_at"], reference)) is not None
        ),
        default=None,
    )
    nearest = evidence.get("nearest")
    overlap: bool | None = None
    if nearest:
        own = {
            row["identity"].strip().lower()
            for row in conn.execute(
                "SELECT identity FROM maintainers WHERE system=? AND name=?",
                (system, name),
            )
            if row["identity"]
        }
        other = {
            row["identity"].strip().lower()
            for row in conn.execute(
                "SELECT identity FROM maintainers WHERE system=? AND name=?",
                (system, nearest),
            )
            if row["identity"]
        }
        if own or other:
            overlap = bool(own & other)

    checks = {
        "active_release": latest_gap is not None and latest_gap <= 365,
        "sufficient_versions": len(versions) >= 5,
        "comprehensive_metadata": bool(package and package["license"] and package["repo_url"]),
        "overlapping_maintainers": overlap,
    }
    benign_hits = sum(1 for value in checks.values() if value is True)
    return {
        "status": "available",
        "nearest": nearest,
        "checks": checks,
        "benign_hits": benign_hits,
        "unavailable": [
            "fork_detection",
            "distinct_purpose",
            "readme_quality",
        ],
    }


def maintainer_exposure(
    conn: sqlite3.Connection, system: str, name: str
) -> dict[str, Any]:
    identities = [
        row["identity"].strip().lower()
        for row in conn.execute(
            "SELECT identity FROM maintainers WHERE system=? AND name=?",
            (system, name),
        )
        if row["identity"]
    ]
    if not identities:
        return {"status": "unknown"}
    placeholders = ",".join("?" for _ in identities)
    rows = conn.execute(
        f"""SELECT DISTINCT p.system, p.name, p.downloads_weekly, p.fan_in_transitive
            FROM maintainers m
            JOIN packages p ON p.system=m.system AND p.name=m.name
            WHERE LOWER(m.identity) IN ({placeholders})
              AND NOT (p.system=? AND p.name=?)""",
        (*identities, system, name),
    ).fetchall()
    packages = sorted(
        (
            {
                "system": row["system"],
                "name": row["name"],
                "downloads_weekly": int(row["downloads_weekly"] or 0),
                "fan_in_transitive": int(row["fan_in_transitive"] or 0),
            }
            for row in rows
        ),
        key=lambda row: (row["downloads_weekly"], row["fan_in_transitive"]),
        reverse=True,
    )
    return {
        "status": "available",
        "identities": identities,
        "other_packages": len(packages),
        "downloads_sum": sum(row["downloads_weekly"] for row in packages),
        "fan_in_transitive_sum": sum(row["fan_in_transitive"] for row in packages),
        "top_packages": packages[:10],
    }


def build_context(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    signal_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "signal_robustness": ROBUSTNESS,
        "typosquat_benignity": typosquat_benignity(
            conn, system, name, signal_map.get("typosquat")
        ),
        "maintainer_exposure": maintainer_exposure(conn, system, name),
    }
