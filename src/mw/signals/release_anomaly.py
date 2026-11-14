from __future__ import annotations

import math
from statistics import median

from ..models import SignalEvidence
from .base import (
    Context,
    clamp,
    days_between,
    median_absolute_deviation,
    parse_ts,
)


def compute(ctx: Context) -> SignalEvidence:
    if ctx.system == "maven":
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "Maven release cadence is not assessed"},
        )

    dates = [parse_ts(v["published_at"]) for v in ctx.versions]
    dates = sorted(d for d in dates if d is not None)
    if len(dates) < 3:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "fewer than 3 dated releases"},
        )

    gaps = [days_between(a, b) for a, b in zip(dates, dates[1:])]
    positive_gaps = [g for g in gaps if g > 0]
    if not positive_gaps:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "all releases share a timestamp"},
        )

    history = [math.log1p(g) for g in positive_gaps]
    med = median(history)
    mad = median_absolute_deviation(history)
    scale = max(mad, 1.0)
    z = (math.log1p(gaps[-1]) - med) / scale

    prior_gap = median(positive_gaps)
    dormancy = 1.0 if gaps[-1] > max(180.0, 6.0 * prior_gap) else 0.0

    last = dates[-1]
    burst = 1.0 if (
        (last - dates[0]).total_seconds() > 48 * 3600
        and sum(1 for d in dates if (last - d).total_seconds() <= 48 * 3600) >= 3
    ) else 0.0

    value = clamp(max(0.8 * dormancy, 0.7 * burst, clamp(z / 5.0)))
    capped = ctx.system == "crates" and burst == 0.0
    if capped:
        value = min(value, 0.5)
    return SignalEvidence(
        value=value,
        evidence={
            "last_gap_days": round(gaps[-1], 1),
            "median_gap_days": round(prior_gap, 1),
            "z_score": round(z, 3),
            "dormancy": dormancy,
            "burst": burst,
            "calibrated_cap": capped,
        },
    )
