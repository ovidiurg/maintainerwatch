from __future__ import annotations

from collections import Counter

from .. import db
from ..models import SignalEvidence
from .base import Context, days_between, now_utc, parse_ts

MIN_COMMITS = 10
MIN_SPAN_DAYS = 180
RECENT_DAYS = 90


def compute(ctx: Context) -> SignalEvidence:
    reference = parse_ts(ctx.as_of) if ctx.as_of else now_utc()
    if reference is None:
        reference = now_utc()
    commits = []
    for row in db.get_commits(ctx.conn, ctx.system, ctx.name):
        when = parse_ts(row["committed_at"])
        if when is not None and when <= reference:
            commits.append((when, row["author_login"] or row["author_email"] or "unknown"))
    if len(commits) < MIN_COMMITS:
        return SignalEvidence(
            value=0.0, applicable=False,
            evidence={"reason": "fewer than 10 commits"},
        )
    commits.sort(key=lambda item: item[0])
    span = days_between(commits[0][0], reference)
    if span < MIN_SPAN_DAYS:
        return SignalEvidence(
            value=0.0, applicable=False,
            evidence={"reason": "commit history shorter than 180 days", "span_days": round(span, 1)},
        )

    recent = [(when, author) for when, author in commits if days_between(when, reference) <= RECENT_DAYS]
    historical = [(when, author) for when, author in commits if days_between(when, reference) > RECENT_DAYS]
    if len(recent) < 5 or not historical:
        return SignalEvidence(
            value=0.0, applicable=False,
            evidence={"reason": "insufficient recent/historical commits"},
        )

    recent_counts = Counter(author for _, author in recent)
    historical_counts = Counter(author for _, author in historical)
    recent_top, recent_count = recent_counts.most_common(1)[0]
    historical_top, historical_count = historical_counts.most_common(1)[0]
    recent_share = recent_count / len(recent)
    historical_share = historical_count / len(historical)

    if recent_top not in historical_counts and recent_share >= 0.5:
        return SignalEvidence(
            value=0.9,
            evidence={
                "reason": "new top author dominates recent commits",
                "recent_top": recent_top,
                "recent_share": round(recent_share, 3),
                "historical_top": historical_top,
            },
        )
    if (
        historical_top != recent_top
        and historical_share >= 0.5
        and recent_share >= 0.5
    ):
        return SignalEvidence(
            value=0.7,
            evidence={
                "reason": "main author handover",
                "recent_top": recent_top,
                "recent_share": round(recent_share, 3),
                "historical_top": historical_top,
                "historical_share": round(historical_share, 3),
            },
        )
    maintainers = db.get_maintainers(ctx.conn, ctx.system, ctx.name)
    if len(maintainers) <= 1 and span >= 365:
        return SignalEvidence(
            value=0.3,
            evidence={
                "reason": "single registered maintainer on a long-lived project",
                "maintainer_count": len(maintainers),
                "span_days": round(span, 1),
            },
        )
    return SignalEvidence(
        value=0.0,
        applicable=False,
        evidence={"reason": "no continuity anomaly"},
    )
