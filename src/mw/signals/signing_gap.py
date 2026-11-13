from __future__ import annotations

from ..models import SignalEvidence
from .base import Context, clamp, days_between, now_utc, parse_ts

RECENT_VERSIONS = 5
YOUNG_PACKAGE_DAYS = 365
MATURE_PACKAGE_DAYS = 730
POPULAR_DOWNLOADS = 100_000
BASELINE_NEW = 1.0
BASELINE_MID = 0.7
BASELINE_OLD = 0.5
BASELINE_OLD_POPULAR = 0.3


def _is_covered(version, system: str) -> bool:
    if system == "npm":
        return bool(version["has_provenance"])
    return bool(version["has_sig"] or version["has_provenance"])


def _baseline_for(ctx: Context, versions) -> tuple[float, float | None]:
    first = parse_ts(versions[0]["published_at"]) if versions else None
    age = days_between(first, now_utc()) if first else None
    if age is None or age < YOUNG_PACKAGE_DAYS:
        return BASELINE_NEW, age
    if age < MATURE_PACKAGE_DAYS:
        return BASELINE_MID, age
    if ctx.downloads_weekly >= POPULAR_DOWNLOADS:
        return BASELINE_OLD_POPULAR, age
    return BASELINE_OLD, age


def compute(ctx: Context) -> SignalEvidence:
    versions = [v for v in ctx.versions if not v["is_yanked"]]
    if not versions:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no non-yanked versions"},
        )
    if ctx.system not in {"npm", "pypi"}:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": f"no signing data for {ctx.system}"},
        )

    ever_covered = [v for v in versions if _is_covered(v, ctx.system)]
    if not ever_covered:
        if ctx.system == "npm":
            baseline, age = _baseline_for(ctx, versions)
            return SignalEvidence(
                value=baseline,
                applicable=True,
                evidence={
                    "reason": "npm package has no provenance in its history",
                    "baseline_unsigned": True,
                    "package_age_days": round(age, 1) if age is not None else None,
                    "downloads_weekly": ctx.downloads_weekly,
                    "versions_checked": len(versions),
                },
            )
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={
                "reason": "no signing or provenance in package history",
                "versions_checked": len(versions),
            },
        )

    recent = versions[-RECENT_VERSIONS:]
    covered = sum(1 for v in recent if _is_covered(v, ctx.system))
    coverage = covered / len(recent)
    return SignalEvidence(
        value=clamp(1.0 - coverage),
        evidence={
            "versions_checked": len(recent),
            "history_versions": len(versions),
            "ever_covered_versions": len(ever_covered),
            "coverage": round(coverage, 4),
        },
    )
