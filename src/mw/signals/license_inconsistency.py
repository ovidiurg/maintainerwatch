from __future__ import annotations

from ..models import SignalEvidence
from .base import Context

KNOWN_MARKERS = (
    "mit", "apache", "bsd", "gpl", "lgpl", "agpl", "mpl", "isc", "unlicense",
    "cc0", "zlib", "epl", "cddl", "artistic", "bsl-1.0", "0bsd", "postgresql",
    "psf", "python", "ncsa", "openssl", "x11", "ms-pl", "ms-rl", "wtfpl",
    "eupl",
)
UNKNOWN = {"unknown", "noassertion", "none", "other", ""}


def compute(ctx: Context) -> SignalEvidence:
    raw = (ctx.license or "").strip()
    if not raw:
        return SignalEvidence(
            value=1.0,
            evidence={"license": None, "reason": "missing license metadata"},
        )
    normalized = raw.lower().replace(" license", "").replace(" licence", "").strip()
    if normalized in UNKNOWN:
        return SignalEvidence(
            value=1.0,
            evidence={"license": raw, "reason": "unknown license metadata"},
        )
    if any(marker in normalized for marker in KNOWN_MARKERS):
        return SignalEvidence(
            value=0.0,
            evidence={"license": raw, "reason": "recognised license family"},
        )
    return SignalEvidence(
        value=0.5,
        evidence={"license": raw, "reason": "not a recognised SPDX identifier"},
    )
