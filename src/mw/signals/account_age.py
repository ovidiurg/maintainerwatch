from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, days_since, piecewise


def compute(ctx: Context) -> SignalEvidence:
    r = ctx.repo
    created = r["owner_created_at"] if r else None
    age = days_since(created)
    if age is None:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "unknown account creation date"},
        )
    value = piecewise(age, [(180, 1.0), (365, 0.6), (730, 0.3), (1e18, 0.0)])
    return SignalEvidence(
        value=value,
        evidence={"account_age_days": round(age, 1)},
    )
