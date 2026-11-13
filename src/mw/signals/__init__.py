from __future__ import annotations

from ..models import SignalEvidence
from . import (
    account_age,
    bus_factor,
    commit_anomaly,
    dependency_risk,
    license_inconsistency,
    publisher_change,
    release_anomaly,
    scorecard,
    signing_gap,
    typosquat,
)
from .base import Context

SIGNALS = {
    "publisher_change": publisher_change.compute,
    "bus_factor": bus_factor.compute,
    "account_age": account_age.compute,
    "release_anomaly": release_anomaly.compute,
    "signing_gap": signing_gap.compute,
    "typosquat": typosquat.compute,
    "license_inconsistency": license_inconsistency.compute,
    "commit_anomaly": commit_anomaly.compute,
    "scorecard": scorecard.compute,
    "dependency_risk": dependency_risk.compute,
}


def compute_all(ctx: Context) -> dict[str, SignalEvidence]:
    return {name: fn(ctx) for name, fn in SIGNALS.items()}
