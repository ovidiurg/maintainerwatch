from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Iterable

from . import db


def _identities_from_value(value: str) -> list[str]:
    identities: list[str] = []
    for part in re.split(r",(?![^<]*>)", value):
        part = part.strip()
        if not part:
            continue
        match = re.search(r"<([^>]+)>", part)
        if match:
            email = match.group(1).strip().lower()
            if email:
                identities.append(email)
            name = part[: match.start()].strip().strip('"').strip()
            if name:
                identities.append(name)
        else:
            cleaned = part.strip().strip('"').strip()
            if cleaned:
                identities.append(cleaned.lower() if "@" in cleaned else cleaned)
    return identities


def parse_metadata_identities(text: str) -> list[str]:
    identities: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() in {
            "author", "author-email", "maintainer", "maintainer-email",
        }:
            identities.extend(_identities_from_value(value))
    return sorted({identity for identity in identities if identity})


def import_snapshot_records(conn: sqlite3.Connection, records: Iterable[dict]) -> int:
    count = 0
    for record in records:
        system = record.get("system")
        name = record.get("name")
        captured_at = record.get("captured_at")
        maintainers = record.get("maintainers") or []
        if not system or not name or not captured_at:
            continue
        payload = json.dumps(sorted(set(maintainers)), sort_keys=True)
        db.record_snapshot(
            conn,
            system,
            name,
            captured_at,
            payload,
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )
        count += 1
    conn.commit()
    return count
