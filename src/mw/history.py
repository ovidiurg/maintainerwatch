from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import db


def _identity(row: sqlite3.Row) -> str:
    value = row["publisher_email"] or row["publisher_name"] or ""
    return value.strip().lower()


def build_history(conn: sqlite3.Connection, system: str, name: str) -> dict[str, Any] | None:
    package = db.get_package(conn, system, name)
    if package is None:
        return None

    versions = conn.execute(
        """SELECT version, published_at, publisher_name, publisher_email,
                  has_sig, has_provenance, is_yanked
           FROM versions WHERE system=? AND name=?
           ORDER BY COALESCE(published_at, ''), version""",
        (system, name),
    ).fetchall()
    snapshots = conn.execute(
        """SELECT captured_at, maintainer_set_json
           FROM snapshots WHERE system=? AND name=?
           ORDER BY captured_at""",
        (system, name),
    ).fetchall()
    maintainers = db.get_maintainers(conn, system, name)

    publisher_changes: list[dict[str, Any]] = []
    previous: tuple[str, str] | None = None
    for row in versions:
        identity = _identity(row)
        raw = row["publisher_email"] or row["publisher_name"]
        if identity and previous and previous[0] != identity:
            publisher_changes.append({
                "at": row["published_at"],
                "version": row["version"],
                "from": previous[1],
                "to": raw,
            })
        if identity:
            previous = (identity, raw)

    snapshot_items = []
    for row in snapshots:
        try:
            values = json.loads(row["maintainer_set_json"] or "[]")
        except (TypeError, ValueError):
            values = []
        snapshot_items.append({
            "captured_at": row["captured_at"],
            "maintainers": sorted(str(value) for value in values if value),
        })

    distinct_publishers = {
        value for value in (
            (row["publisher_email"] or row["publisher_name"] or "").strip().lower()
            for row in versions
        ) if value
    }
    return {
        "system": system,
        "name": name,
        "summary": {
            "versions": len(versions),
            "first_version_at": versions[0]["published_at"] if versions else None,
            "latest_version_at": versions[-1]["published_at"] if versions else None,
            "distinct_publishers": len(distinct_publishers),
            "publisher_changes": len(publisher_changes),
            "snapshots": len(snapshot_items),
            "current_maintainers": len(maintainers),
        },
        "publisher_changes": publisher_changes[-100:],
        "snapshots": snapshot_items[-50:],
        "maintainers": [
            {
                "identity": row["identity"],
                "role": row["role"],
                "source": row["source"],
                "account_created_at": row["account_created_at"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }
            for row in maintainers
        ],
        "recent_versions": [
            {
                "version": row["version"],
                "published_at": row["published_at"],
                "publisher_name": row["publisher_name"],
                "publisher_email": row["publisher_email"],
                "has_sig": bool(row["has_sig"]),
                "has_provenance": bool(row["has_provenance"]),
                "is_yanked": bool(row["is_yanked"]),
            }
            for row in versions[-100:]
        ],
    }
