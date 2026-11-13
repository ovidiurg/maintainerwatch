from __future__ import annotations

import json
import re
from datetime import timedelta

from .. import db
from ..models import SignalEvidence
from ..resolve import canonical
from .base import Context, clamp, days_between, now_utc, parse_ts
from .legitimacy import assess_change

WINDOW_DAYS = 365
SNAPSHOT_MIN_AGE_DAYS = 180
SNAPSHOT_MAX_AGE_DAYS = 365


def _is_automation(value: str | None, auto_ids: set[str], auto_res: list[re.Pattern]) -> bool:
    if not value:
        return False
    key = value.strip().lower()
    return key in auto_ids or any(r.search(key) for r in auto_res)


def _release_changes(ctx: Context, versions, reference, is_automation):
    changes: list[dict] = []
    prev: tuple[str, str, str] | None = None
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
                    "from_raw": prev[1],
                    "to_raw": raw,
                    "version": v["version"],
                    "at": v["published_at"],
                }
            )
        prev = (ident, raw, v["version"])

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

    previous = {
        str(item).strip().lower()
        for item in json.loads(snapshot["maintainer_set_json"] or "[]")
        if item
    }
    current = {
        str(row["identity"]).strip().lower()
        for row in db.get_maintainers(ctx.conn, ctx.system, ctx.name)
        if row["identity"]
    }
    if not current:
        latest = db.get_latest_snapshot(ctx.conn, ctx.system, ctx.name)
        if latest is not None:
            current = {
                str(item).strip().lower()
                for item in json.loads(latest["maintainer_set_json"] or "[]")
                if item
            }
    if not current:
        return None

    added = sorted(current - previous)
    removed = sorted(previous - current)
    captured = parse_ts(snapshot["captured_at"])
    age = round(days_between(captured, reference), 1) if captured else None
    if age is None or age > SNAPSHOT_MAX_AGE_DAYS:
        return None
    return {
        "snapshot_at": snapshot["captured_at"],
        "snapshot_age_days": age,
        "added": added,
        "removed": removed,
        "n_changed": len(added) + len(removed),
        "overlap": len(previous & current),
        "previous_count": len(previous),
        "current_count": len(current),
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
        effective = 0.0
        recent_with_context = []
        for change in recent:
            context = assess_change(
                ctx.conn, ctx.system, ctx.name,
                change["from"], change["to"],
                change.get("from_raw"), change.get("to_raw"), change.get("at"),
                ctx.identity_mapping,
            )
            effective += context["discount"]
            recent_with_context.append({**change, "legitimacy": context})
        return SignalEvidence(
            value=clamp(effective / 2.0),
            evidence={
                "source": "releases",
                "n_changes": len(changes),
                "n_recent": len(recent),
                "n_legitimate": sum(
                    1 for change in recent_with_context
                    if change["legitimacy"]["discount"] < 1.0
                ),
                "recent_changes": recent_with_context[-10:],
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
                    "no per-release publisher and no snapshot between "
                    f"{SNAPSHOT_MIN_AGE_DAYS} and {SNAPSHOT_MAX_AGE_DAYS} days old"
                )
            },
        )

    discount = 0.7 if snapshot["overlap"] else 1.0
    return SignalEvidence(
        value=min(0.5, clamp(snapshot["n_changed"] / 2.0)) * discount,
        evidence={
            "source": "snapshot",
            **snapshot,
            "n_recent": 1 if snapshot["n_changed"] else 0,
            "legitimacy": {
                "overlap": snapshot["overlap"],
                "discount": discount,
                "reason": "some maintainers remain" if snapshot["overlap"] else "full replacement",
            },
        },
    )
