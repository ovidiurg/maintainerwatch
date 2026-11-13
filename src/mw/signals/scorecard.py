from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, clamp


def compute(ctx: Context) -> SignalEvidence:
    repo = ctx.repo
    score = repo["scorecard_score"] if repo else None
    if score is None:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no OpenSSF Scorecard data"},
        )

    score = float(score)
    return SignalEvidence(
        value=clamp((7.0 - score) / 7.0),
        evidence={"scorecard_score": score, "reference": 7.0},
    )
