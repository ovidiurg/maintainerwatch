from __future__ import annotations

from mw.risk import describe_risk


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
