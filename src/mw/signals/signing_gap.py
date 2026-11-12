from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, clamp


def compute(ctx: Context) -> SignalEvidence:
    versions = [v for v in ctx.versions if not v["is_yanked"]][-5:]
    if not versions:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no non-yanked versions"},
        )

    if ctx.system == "npm":
        covered = sum(1 for v in versions if v["has_provenance"]) / len(versions)
    else:
        covered = sum(
            1 for v in versions if v["has_sig"] or v["has_provenance"]
        ) / len(versions)

    return SignalEvidence(
        value=clamp(1.0 - covered),
        evidence={
            "versions_checked": len(versions),
            "coverage": round(covered, 4),
        },
    )
