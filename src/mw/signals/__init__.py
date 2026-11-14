from __future__ import annotations

from ..models import SignalEvidence
from . import (
    account_age,
    bus_factor,
    commit_anomaly,
    dependency_risk,
    install_script,
    license_inconsistency,
    publisher_change,
    release_anomaly,
    scorecard,
    signing_gap,
    typosquat,
)
from .base import Context
from .guards import apply_cross_signal_guards

SIGNALS = {
    "publisher_change": publisher_change.compute,
    "bus_factor": bus_factor.compute,
    "account_age": account_age.compute,
    "release_anomaly": release_anomaly.compute,
    "signing_gap": signing_gap.compute,
    "typosquat": typosquat.compute,
    "license_inconsistency": license_inconsistency.compute,
    "install_script": install_script.compute,
    "commit_anomaly": commit_anomaly.compute,
    "scorecard": scorecard.compute,
    "dependency_risk": dependency_risk.compute,
}


def compute_all(ctx: Context) -> dict[str, SignalEvidence]:
    signals = {name: fn(ctx) for name, fn in SIGNALS.items()}
    return apply_cross_signal_guards(signals)
