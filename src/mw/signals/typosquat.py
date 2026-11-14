from __future__ import annotations

from ..models import SignalEvidence
from .base import Context

TARGET_MIN_DOWNLOADS = 100_000


def levenshtein(a: str, b: str) -> int:
    """Damerau-Levenshtein (optimal string alignment), so transpositions count once."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )
            if (
                i > 1
                and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)
    return d[la][lb]


def compute(ctx: Context) -> SignalEvidence:
    if not ctx.top_names:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no top package list available"},
        )

    name = ctx.name.lower()
    best: tuple[int, str | None] = (999, None)
    for candidate in ctx.top_names:
        other = candidate.lower()
        if other == name or abs(len(other) - len(name)) > 2:
            continue
        distance = levenshtein(name, other)
        if distance < best[0]:
            best = (distance, other)
            if distance == 1:
                break

    distance, nearest = best
    suspicious = distance == 1 or (distance == 2 and len(name) > 8)
    if suspicious and ctx.downloads_weekly < 1000:
        value = 1.0
    elif suspicious:
        value = 0.2
    else:
        value = 0.0

    return SignalEvidence(
        value=value,
        evidence={
            "distance": distance,
            "nearest": nearest,
            "downloads_weekly": ctx.downloads_weekly,
        },
    )
