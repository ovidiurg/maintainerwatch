from __future__ import annotations

import re

from ..models import SignalEvidence
from .base import Context

KNOWN_MARKERS = (
    "mit", "apache", "bsd", "gpl", "lgpl", "agpl", "mpl", "isc", "unlicense",
    "cc0", "zlib", "epl", "cddl", "artistic", "bsl-1.0", "0bsd", "postgresql",
    "psf", "python", "ncsa", "openssl", "x11", "ms-pl", "ms-rl", "wtfpl",
    "eupl",
)
UNKNOWN = {"unknown", "noassertion", "none", "other", ""}

ALIASES = {
    "mit": "mit",
    "apache2": "apache-2.0",
    "apache2.0": "apache-2.0",
    "apache-2.0": "apache-2.0",
    "bsd2": "bsd-2-clause",
    "bsd2-clause": "bsd-2-clause",
    "bsd-2-clause": "bsd-2-clause",
    "bsd3": "bsd-3-clause",
    "bsd3-clause": "bsd-3-clause",
    "bsd-3-clause": "bsd-3-clause",
    "isc": "isc",
    "mpl2": "mpl-2.0",
    "mpl2.0": "mpl-2.0",
    "mpl-2.0": "mpl-2.0",
    "gpl2": "gpl-2.0",
    "gpl2.0": "gpl-2.0",
    "gpl-2.0": "gpl-2.0",
    "gpl3": "gpl-3.0",
    "gpl3.0": "gpl-3.0",
    "gpl-3.0": "gpl-3.0",
    "lgpl2.1": "lgpl-2.1",
    "lgpl-2.1": "lgpl-2.1",
    "lgpl3": "lgpl-3.0",
    "lgpl3.0": "lgpl-3.0",
    "lgpl-3.0": "lgpl-3.0",
    "agpl3": "agpl-3.0",
    "agpl3.0": "agpl-3.0",
    "agpl-3.0": "agpl-3.0",
    "epl2": "epl-2.0",
    "epl2.0": "epl-2.0",
    "epl-2.0": "epl-2.0",
    "cddl1": "cddl-1.0",
    "cddl1.0": "cddl-1.0",
    "cddl-1.0": "cddl-1.0",
    "artistic2": "artistic-2.0",
    "artistic2.0": "artistic-2.0",
    "artistic-2.0": "artistic-2.0",
    "bsl1": "bsl-1.0",
    "bsl1.0": "bsl-1.0",
    "bsl-1.0": "bsl-1.0",
    "0bsd": "0bsd",
    "unlicense": "unlicense",
    "cc0": "cc0-1.0",
    "cc01.0": "cc0-1.0",
    "cc0-1.0": "cc0-1.0",
    "zlib": "zlib",
    "wtfpl": "wtfpl",
    "postgresql": "postgresql",
    "psf2": "psf-2.0",
    "psf2.0": "psf-2.0",
    "python2.0": "python-2.0",
    "ncsa": "ncsa",
    "openssl": "openssl",
    "x11": "x11",
    "ms-pl": "ms-pl",
    "ms-rl": "ms-rl",
    "eupl1.2": "eupl-1.2",
    "eupl-1.2": "eupl-1.2",
    "publicdomain": "public-domain",
}


def _normalize_token(part: str) -> str | None:
    text = part.lower()
    text = re.sub(r"\b(the|license|licence|version)\b", " ", text)
    text = re.sub(r"(?<=[a-z])v(?=\d)", "", text)
    text = re.sub(r"[^a-z0-9.\-]", "", text)
    text = text.strip("-.")
    text = re.sub(r"-(only|or-later)$", "", text)
    if not text:
        return None

    if text in ALIASES:
        return ALIASES[text]

    if text.startswith("cc0"):
        return "cc0-1.0"
    if "gnugeneralpublic" in text or "generalpublic" in text:
        if "affero" in text or "agpl" in text:
            return "agpl-3.0"
        if "lesser" in text or "lgpl" in text or "library" in text:
            if "2.1" in text:
                return "lgpl-2.1"
            return "lgpl-3.0"
        if "2" in text:
            return "gpl-2.0"
        return "gpl-3.0"
    if "mozillapublic" in text:
        return "mpl-1.1" if "1.1" in text else "mpl-2.0"
    if "eclipsepublic" in text:
        return "epl-2.0" if "2" in text else "epl-1.0"
    if "boostsoftware" in text:
        return "bsl-1.0"
    if "artistic" in text:
        return "artistic-2.0"
    if "microsoftpublic" in text:
        return "ms-pl"
    if "microsoftreciprocal" in text:
        return "ms-rl"
    if "pythonsoftwarefoundation" in text:
        return "psf-2.0"
    if text.startswith("apache"):
        return "apache-2.0"
    if text.startswith("mit"):
        return "mit"
    if text.startswith("isc"):
        return "isc"
    if text.startswith("unlicense"):
        return "unlicense"
    return None


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    parts = re.split(r"\s+or\s+|\s+and\s+|/|\|", value, flags=re.IGNORECASE)
    return {token for part in parts if (token := _normalize_token(part))}


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
        value = 0.0
        reason = "recognised license family"
    else:
        value = 0.5
        reason = "not a recognised SPDX identifier"

    primary_tokens = _tokens(raw)
    classifier_tokens = _tokens(ctx.license_classifier)
    repo_tokens = _tokens(ctx.license_repo)
    conflicts: list[str] = []

    if primary_tokens and classifier_tokens and not (primary_tokens & classifier_tokens):
        conflicts.append("classifier")
    if primary_tokens and repo_tokens and not (primary_tokens & repo_tokens):
        conflicts.append("repository")

    if conflicts:
        value = 1.0
        reason = "license sources disagree"

    return SignalEvidence(
        value=value,
        evidence={
            "license": raw,
            "classifier": ctx.license_classifier,
            "repository": ctx.license_repo,
            "tokens": sorted(primary_tokens),
            "classifier_tokens": sorted(classifier_tokens),
            "repository_tokens": sorted(repo_tokens),
            "conflicts": conflicts,
            "reason": reason,
        },
    )
