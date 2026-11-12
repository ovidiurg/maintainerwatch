from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .models import SignalEvidence


def band_for(score: float) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    return "high"


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_score(
    signals: dict[str, SignalEvidence],
    weights: dict[str, int],
    model_version: str,
) -> tuple[float, str, str]:
    applicable = {
        name: sig
        for name, sig in signals.items()
        if sig.applicable and name in weights
    }
    total_weight = sum(weights[name] for name in applicable)
    if not total_weight:
        return 0.0, "low", hashlib.sha256(
            _canonical({"model_version": model_version, "signals": {}}).encode()
        ).hexdigest()

    weighted = sum(weights[name] * sig.value for name, sig in applicable.items())
    score = round(100.0 * weighted / total_weight, 1)

    inputs = {
        "model_version": model_version,
        "signals": {
            name: [round(sig.value, 4), sig.evidence]
            for name, sig in sorted(applicable.items())
        },
    }
    digest = hashlib.sha256(_canonical(inputs).encode("utf-8")).hexdigest()
    return score, band_for(score), digest


def computed_at() -> str:
    return datetime.now(timezone.utc).isoformat()
