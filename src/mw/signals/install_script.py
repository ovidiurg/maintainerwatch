from __future__ import annotations

import re

from ..models import SignalEvidence
from .base import Context

HIGH_RISK = [
    re.compile(r"\b(curl|wget)\b", re.I),
    re.compile(r"\bbase64\b", re.I),
    re.compile(r"\beval\s*\(", re.I),
    re.compile(r"child_process", re.I),
    re.compile(r"\bpowershell\b", re.I),
    re.compile(r"\bcmd(?:\.exe)?\s*/c\b", re.I),
    re.compile(r"\bchmod\s+\+x\b", re.I),
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"require\(['\"]https?['\"]\)", re.I),
    re.compile(r"\bfetch\s*\(", re.I),
]
MEDIUM_RISK = [
    re.compile(r"https?://", re.I),
    re.compile(r"\bnode\s+-e\b", re.I),
    re.compile(r"\bprocess\.env\b", re.I),
]


def compute(ctx: Context) -> SignalEvidence:
    versions = [
        version
        for version in ctx.versions
        if not version["is_yanked"] and version["install_script"]
    ][-5:]
    if not versions:
        return SignalEvidence(
            value=0.0,
            applicable=False,
            evidence={"reason": "no install scripts in recent versions"},
        )

    scripts = [version["install_script"] for version in versions]
    combined = "\n".join(scripts)
    high = sorted({match.group(0).lower() for pattern in HIGH_RISK for match in pattern.finditer(combined)})
    medium = sorted({match.group(0).lower() for pattern in MEDIUM_RISK for match in pattern.finditer(combined)})
    if high:
        value = 1.0
    elif medium:
        value = 0.5
    else:
        value = 0.3

    return SignalEvidence(
        value=value,
        evidence={
            "versions_checked": len(versions),
            "high_risk_patterns": high,
            "medium_risk_patterns": medium,
            "scripts": [script[:500] for script in scripts],
        },
    )
