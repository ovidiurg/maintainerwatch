from __future__ import annotations

import math

from ..models import SignalEvidence
from .base import Context, clamp


def compute(ctx: Context) -> SignalEvidence:
    fan_in = int(ctx.fan_in_transitive or 0)
    dependencies = int(ctx.dependencies_count or 0)
    if fan_in == 0 and dependencies == 0:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no dependency graph data"},
        )

    fan_in_value = clamp(math.log1p(fan_in) / math.log1p(200))
    fan_out_value = clamp(math.log1p(dependencies) / math.log1p(100)) * 0.3
    value = clamp(max(fan_in_value, fan_out_value))
    return SignalEvidence(
        value=value,
        evidence={
            "fan_in_transitive": fan_in,
            "dependencies_count": dependencies,
            "fan_in_value": round(fan_in_value, 3),
            "fan_out_value": round(fan_out_value, 3),
        },
    )
