from __future__ import annotations

from mw.models import SignalEvidence
from mw.signals.guards import apply_cross_signal_guards


def _baseline_gap(value: float = 0.3) -> SignalEvidence:
    return SignalEvidence(
        value=value,
        applicable=True,
        evidence={"baseline_unsigned": True},
    )


def test_publisher_change_guard_raises_unsigned_baseline():
    signals = {
        "signing_gap": _baseline_gap(),
        "publisher_change": SignalEvidence(
            value=0.5,
            applicable=True,
            evidence={"n_legitimate": 0},
        ),
    }
    guarded = apply_cross_signal_guards(signals)
    assert guarded["signing_gap"].value == 1.0
    assert guarded["signing_gap"].evidence["cross_signal_guard"][
        "publisher_changes_without_legitimacy"
    ] is True


def test_legitimate_publisher_change_does_not_trigger_guard():
    signals = {
        "signing_gap": _baseline_gap(),
        "publisher_change": SignalEvidence(
            value=0.8,
            applicable=True,
            evidence={"n_legitimate": 1},
        ),
    }
    guarded = apply_cross_signal_guards(signals)
    assert guarded["signing_gap"].value == 0.3


def test_commit_anomaly_guard_raises_unsigned_baseline():
    signals = {
        "signing_gap": _baseline_gap(),
        "commit_anomaly": SignalEvidence(value=0.9, applicable=True),
    }
    guarded = apply_cross_signal_guards(signals)
    assert guarded["signing_gap"].value == 1.0
    assert guarded["signing_gap"].evidence["cross_signal_guard"][
        "commit_anomaly_strong"
    ] is True


def test_guard_ignores_non_baseline_signing_gap():
    signals = {
        "signing_gap": SignalEvidence(value=0.5, applicable=True),
        "commit_anomaly": SignalEvidence(value=1.0, applicable=True),
    }
    guarded = apply_cross_signal_guards(signals)
    assert guarded["signing_gap"].value == 0.5
