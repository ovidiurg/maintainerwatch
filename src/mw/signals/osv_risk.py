from __future__ import annotations

from .. import db
from ..models import SignalEvidence
from ..osv_match import affected
from .base import Context


def compute(ctx: Context) -> SignalEvidence:
    rows = db.get_osv(ctx.conn, ctx.system, ctx.name)
    versions = [version for version in ctx.versions if not version["is_yanked"]]
    if not rows or not versions:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no OSV data or versions"},
        )

    current = versions[-1]["version"]
    matches = [
        row for row in rows
        if affected(row["affected_json"], ctx.system, ctx.name, current)
    ]
    if not matches:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={
                "reason": "no advisory affects the current version",
                "current_version": current,
                "advisories_checked": len(rows),
            },
        )

    malicious = [row["vuln_id"] for row in matches if row["vuln_id"].startswith("MAL-")]
    return SignalEvidence(
        value=1.0 if malicious else 0.5,
        evidence={
            "current_version": current,
            "advisories": [row["vuln_id"] for row in matches],
            "malicious_advisories": malicious,
        },
    )
