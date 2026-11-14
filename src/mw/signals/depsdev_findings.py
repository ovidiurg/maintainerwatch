from __future__ import annotations

import json

from .. import db
from ..models import SignalEvidence
from .base import Context


def _findings(doc: dict) -> list[dict]:
    out: list[dict] = []
    for key in ("packageFindings",):
        out.extend(doc.get(key) or [])
    for key in ("requestedVersion", "defaultVersion"):
        version = doc.get(key) or {}
        out.extend(version.get("findings") or [])
    return [item for item in out if isinstance(item, dict)]


def _value(findings: list[dict]) -> tuple[float, list[str]]:
    types = {str(item.get("type")) for item in findings}
    if "MALICIOUS" in types:
        return 1.0, sorted(types)
    if "VULNERABLE" in types:
        return 0.5, sorted(types)
    if "DEPRECATED" in types:
        return 0.4, sorted(types)
    if "LOW_USAGE" in types:
        return 0.3, sorted(types)
    if "COOLDOWN" in types:
        return 0.2, sorted(types)
    return 0.2, sorted(types)


def compute(ctx: Context) -> SignalEvidence:
    row = db.get_findings(ctx.conn, ctx.system, ctx.name)
    if row is None:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no deps.dev findings data"},
        )
    try:
        doc = json.loads(row["findings_json"] or "{}")
    except (TypeError, ValueError):
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "invalid findings payload"},
        )
    findings = _findings(doc)
    if not findings:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no deps.dev findings", "version": row["version"]},
        )
    value, types = _value(findings)
    return SignalEvidence(
        value=value,
        evidence={
            "version": row["version"],
            "finding_types": types,
            "risks": sorted({str(item.get("risk")) for item in findings}),
        },
    )
