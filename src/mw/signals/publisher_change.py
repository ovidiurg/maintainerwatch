from __future__ import annotations

import re

from ..models import SignalEvidence
from ..resolve import canonical
from .base import Context, clamp, days_between, now_utc, parse_ts

WINDOW_DAYS = 365


def compute(ctx: Context) -> SignalEvidence:
    versions = [v for v in ctx.versions if v["published_at"]]
    if len(versions) < 2:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "fewer than 2 dated versions"},
        )

    auto_ids = {i.strip().lower() for i in ctx.automation_identities}
    auto_res = [re.compile(p) for p in ctx.automation_patterns]

    def is_automation(value: str | None) -> bool:
        if not value:
            return False
        key = value.strip().lower()
        if key in auto_ids:
            return True
        return any(r.search(key) for r in auto_res)

    reference = parse_ts(ctx.as_of) if ctx.as_of else now_utc()
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
    for c in changes:
        when = parse_ts(c["at"])
        if when and reference and days_between(when, reference) <= WINDOW_DAYS:
            recent.append(c)
    value = clamp(len(recent) / 2.0)
    return SignalEvidence(
        value=value,
        evidence={
            "n_changes": len(changes),
            "n_recent": len(recent),
            "changes": changes[-10:],
        },
    )
