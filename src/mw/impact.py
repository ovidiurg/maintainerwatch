from __future__ import annotations

import math


def impact_score(
    dependent_count: int | None,
    downloads_weekly: int | None,
    fan_in_transitive: int | None,
) -> float:
    dependents = math.log1p(max(int(dependent_count or 0), 0)) / math.log1p(1_000_000)
    downloads = math.log1p(max(int(downloads_weekly or 0), 0)) / math.log1p(1_000_000_000)
    fan_in = math.log1p(max(int(fan_in_transitive or 0), 0)) / math.log1p(500)
    return round(
        100.0
        * (0.5 * min(dependents, 1.0) + 0.3 * min(downloads, 1.0) + 0.2 * min(fan_in, 1.0)),
        1,
    )


def impact_tier(count: int | None) -> str:
    if not count:
        return "unknown"
    if count >= 1000:
        return "critical"
    if count >= 100:
        return "high"
    if count >= 10:
        return "medium"
    return "low"
