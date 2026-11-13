from __future__ import annotations

from ..models import SignalEvidence
from .base import Context


def compute(ctx: Context) -> SignalEvidence:
    versions = [
        v for v in ctx.versions
        if not v["is_yanked"] and v["publisher_key_id"]
    ][-10:]
    if not versions:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no signing key data"},
        )

    keys = sorted({v["publisher_key_id"] for v in versions})
    return SignalEvidence(
        value=1.0 if len(keys) > 1 else 0.0,
        evidence={
            "keys": keys,
            "versions_checked": len(versions),
        },
    )
