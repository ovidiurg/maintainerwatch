from __future__ import annotations

from mw.models import SignalEvidence
from mw.risk import describe_risk, has_high_confidence


def _sig(value, **evidence):
    return {"value": value, "evidence": evidence}


def test_dormant_concentrated_project():
    risk_type, note, next_step = describe_risk({
        "release_anomaly": _sig(0.8, last_gap_days=1061.0, median_gap_days=145.3),
        "bus_factor": _sig(0.8745, top_author_share=0.8745),
    })
    assert risk_type == "Dormant, concentrated project"
    assert "1061" in note
    assert "maintainer" in next_step


def test_maintainer_takeover():
    risk_type, note, next_step = describe_risk({
        "publisher_change": _sig(0.5, n_legitimate=0),
    })
    assert risk_type == "Maintainer takeover"
    assert "handover" in note
    assert "out-of-band" in next_step


def test_typosquat():
    risk_type, note, _ = describe_risk({
        "typosquat": _sig(1.0, nearest="requests"),
    })
    assert risk_type == "Possible typosquat"
    assert "requests" in note


def test_general_fallback():
    risk_type, _, next_step = describe_risk({})
    assert risk_type == "General risk"
    assert next_step


def test_high_confidence_requires_behavioral_signal():
    assert has_high_confidence({"publisher_change": _sig(0.5)}) is True
    assert has_high_confidence({"osv_risk": _sig(1.0)}) is True
    assert has_high_confidence({"release_anomaly": _sig(1.0)}) is False
    assert has_high_confidence({"signing_gap": _sig(1.0)}) is False


def test_high_confidence_accepts_signal_evidence():
    assert has_high_confidence({
        "publisher_change": SignalEvidence(value=0.5),
    }) is True


def test_high_confidence_commit_anomaly_needs_new_author():
    burst_only = {
        "commit_anomaly": {
            "value": 1.0,
            "evidence": {"new_author_share": 0.0, "new_author_value": 0.0},
        }
    }
    assert has_high_confidence(burst_only) is False
    assert has_high_confidence({
        "commit_anomaly": {
            "value": 1.0,
            "evidence": {"new_author_share": 0.7, "new_author_value": 0.4},
        }
    }) is True


def test_high_confidence_platform_gate():
    assert has_high_confidence({"publisher_change": _sig(0.75)}, system="github") is False
    assert has_high_confidence({"commit_anomaly": _sig(0.99)}, system="maven") is False
    assert has_high_confidence({"publisher_change": _sig(0.75)}, system="npm") is True
    assert has_high_confidence({"osv_risk": _sig(1.0)}, system="maven") is True
