from __future__ import annotations

import json
import re
from datetime import timedelta

from .. import db
from ..models import SignalEvidence
from ..resolve import canonical
from .base import Context, clamp, days_between, now_utc, parse_ts

WINDOW_DAYS = 365
SNAPSHOT_MIN_AGE_DAYS = 180


def _is_automation(value: str | None, auto_ids: set[str], auto_res: list[re.Pattern]) -> bool:
    if not value:
        return False
    key = value.strip().lower()
    return key in auto_ids or any(r.search(key) for r in auto_res)


def _release_changes(ctx: Context, versions, reference, is_automation):
    changes: list[dict] = []
    prev: tuple[str, str] | None = None
    for v in versions:
        raw = v["publisher_email"] or v["publisher_name"]
        ident = canonical(raw, ctx.identity_mapping)
        if not ident or is_automation(raw) or is_automation(ident):
            continue
        if prev and prev[0] != ident:
            changes.append(
                {
                    "from": prev[0],
                    "to": ident,
                    "version": v["version"],
                    "at": v["published_at"],
                }
            )
        prev = (ident, v["version"])

    recent = []
    for change in changes:
        when = parse_ts(change["at"])
        if when and days_between(when, reference) <= WINDOW_DAYS:
            recent.append(change)
    return changes, recent


def _snapshot_changes(ctx: Context, reference) -> dict | None:
    cutoff = reference - timedelta(days=SNAPSHOT_MIN_AGE_DAYS)
    snapshot = db.get_snapshot_before(
        ctx.conn, ctx.system, ctx.name, cutoff.isoformat()
    )
    if snapshot is None:
        return None

    previous = set(json.loads(snapshot["maintainer_set_json"] or "[]"))
    current = {
        row["identity"]
        for row in db.get_maintainers(ctx.conn, ctx.system, ctx.name)
        if row["identity"]
    }
    if not current:
        latest = db.get_latest_snapshot(ctx.conn, ctx.system, ctx.name)
        if latest is not None:
            current = set(json.loads(latest["maintainer_set_json"] or "[]"))

    added = sorted(current - previous)
    removed = sorted(previous - current)
    captured = parse_ts(snapshot["captured_at"])
    age = round(days_between(captured, reference), 1) if captured else None
    return {
        "snapshot_at": snapshot["captured_at"],
        "snapshot_age_days": age,
        "added": added,
        "removed": removed,
        "n_changed": len(added) + len(removed),
    }


def compute(ctx: Context) -> SignalEvidence:
    versions = [v for v in ctx.versions if v["published_at"]]
    reference = parse_ts(ctx.as_of) if ctx.as_of else now_utc()
    if reference is None:
        reference = now_utc()

    auto_ids = {i.strip().lower() for i in ctx.automation_identities}
    auto_res = [re.compile(p) for p in ctx.automation_patterns]

    def is_automation(value: str | None) -> bool:
        return _is_automation(value, auto_ids, auto_res)

    changes, recent = _release_changes(ctx, versions, reference, is_automation)

    # npm exposes a per-release publisher, so release history is authoritative.
    if ctx.system == "npm" or changes:
        if len(versions) < 2 and not changes:
            return SignalEvidence(
                value=0.0,
                applicable=False,
                evidence={"reason": "fewer than 2 dated versions"},
            )
        return SignalEvidence(
            value=clamp(len(recent) / 2.0),
            evidence={
                "source": "releases",
                "n_changes": len(changes),
                "n_recent": len(recent),
                "changes": changes[-10:],
            },
        )

    # PyPI, crates.io and Maven do not expose a per-release publisher here;
    # fall back to a maintainer snapshot at least SNAPSHOT_MIN_AGE_DAYS old.
    snapshot = _snapshot_changes(ctx, reference)
    if snapshot is None:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={
                "reason": (
                    "no per-release publisher and no snapshot older than "
                    f"{SNAPSHOT_MIN_AGE_DAYS} days"
                )
            },
        )

    return SignalEvidence(
        value=clamp(snapshot["n_changed"] / 2.0),
        evidence={
            "source": "snapshot",
            **snapshot,
            "n_recent": 1 if snapshot["n_changed"] else 0,
        },
    )
