from __future__ import annotations

from collections import Counter

from .. import db
from ..models import SignalEvidence
from .base import Context, clamp, days_between, now_utc, parse_ts

WINDOW_DAYS = 90
NEW_AUTHOR_DAYS = 90
MIN_COMMITS = 5


def compute(ctx: Context) -> SignalEvidence:
    reference = parse_ts(ctx.as_of) if ctx.as_of else now_utc()
    if reference is None:
        reference = now_utc()

    rows = db.get_commits(ctx.conn, ctx.system, ctx.name)
    commits: list[tuple] = []
    for row in rows:
        when = parse_ts(row["committed_at"])
        if when is not None and when <= reference:
            commits.append((when, row["author_login"] or row["author_email"] or "unknown"))
    if len(commits) < MIN_COMMITS:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "fewer than 5 commits"},
        )

    commits.sort(key=lambda item: item[0])
    window = [item for item in commits if days_between(item[0], reference) <= WINDOW_DAYS]
    if len(window) < MIN_COMMITS:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "fewer than 5 commits in the last 90 days"},
        )

    first_seen: dict[str, object] = {}
    for when, author in commits:
        first_seen.setdefault(author, when)
    new_authors = {
        author
        for author, when in first_seen.items()
        if days_between(when, reference) <= NEW_AUTHOR_DAYS
    }

    new_commits = [item for item in window if item[1] in new_authors]
    new_share = len(new_commits) / len(window)
    new_value = clamp((new_share - 0.5) / 0.5)

    last_30 = sum(1 for when, _ in window if days_between(when, reference) <= 30)
    previous = [
        when
        for when, _ in commits
        if 30 < days_between(when, reference) <= 120
    ]
    previous_avg_30 = len(previous) / 3.0
    burst_ratio = (last_30 / previous_avg_30) if previous_avg_30 else float(last_30)
    burst_value = (
        clamp((burst_ratio - 2.0) / 4.0) if last_30 >= 10 else 0.0
    )

    counts = Counter(author for _, author in window)
    top_share = max(counts.values()) / len(window) if counts else 0.0

    value = clamp(max(new_value, burst_value))
    return SignalEvidence(
        value=value,
        evidence={
            "commits_window": len(window),
            "new_authors": sorted(new_authors),
            "new_author_share": round(new_share, 3),
            "new_author_value": round(new_value, 3),
            "last_30_days": last_30,
            "previous_30_day_avg": round(previous_avg_30, 2),
            "burst_ratio": round(burst_ratio, 2),
            "burst_value": round(burst_value, 3),
            "top_author_share": round(top_share, 3),
        },
    )
