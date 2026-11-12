from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, clamp


def compute(ctx: Context) -> SignalEvidence:
    r = ctx.repo
    if not r or not r["contributors_12m"]:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no repository contributor data"},
        )
    share = float(r["top_author_share"] or 0.0)
    n = int(r["contributors_12m"] or 0)
    return SignalEvidence(
        value=clamp(share),
        evidence={
            "contributors_12m": n,
            "top_author_share": round(share, 4),
        },
    )
