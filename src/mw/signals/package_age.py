from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, days_between, now_utc, parse_ts


def compute(ctx: Context) -> SignalEvidence:
    dates = [parse_ts(v["published_at"]) for v in ctx.versions]
    dates = [date for date in dates if date is not None]
    if not dates:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no dated releases before cutoff"},
        )
    reference = parse_ts(ctx.as_of) if ctx.as_of else now_utc()
    age = days_between(min(dates), reference)
    if age < 30:
        value = 1.0
    elif age < 180:
        value = 0.8
    elif age < 365:
        value = 0.4
    else:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "package older than one year", "package_age_days": round(age, 1)},
        )
    return SignalEvidence(
        value=value,
        evidence={"package_age_days": round(age, 1)},
    )
