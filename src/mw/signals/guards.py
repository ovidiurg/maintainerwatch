from __future__ import annotations

from ..models import SignalEvidence

GUARD_PUBLISHER_CHANGE = 0.5
GUARD_COMMIT_ANOMALY = 0.75
GUARD_VALUE = 1.0


def apply_cross_signal_guards(
    signals: dict[str, SignalEvidence],
) -> dict[str, SignalEvidence]:
    gap = signals.get("signing_gap")
    if gap is None or not gap.applicable or not gap.evidence.get("baseline_unsigned"):
        return signals

    publisher = signals.get("publisher_change")
    commit = signals.get("commit_anomaly")
    publisher_value = publisher.value if publisher and publisher.applicable else 0.0
    commit_value = commit.value if commit and commit.applicable else 0.0
    publisher_strong = (
        publisher is not None
        and publisher.applicable
        and publisher_value >= GUARD_PUBLISHER_CHANGE
        and int(publisher.evidence.get("n_legitimate", 0)) == 0
    )
    commit_strong = commit_value >= GUARD_COMMIT_ANOMALY
    if not (publisher_strong or commit_strong):
        return signals

    evidence = dict(gap.evidence)
    evidence["cross_signal_guard"] = {
        "publisher_change": round(publisher_value, 4),
        "commit_anomaly": round(commit_value, 4),
        "publisher_changes_without_legitimacy": publisher_strong,
        "commit_anomaly_strong": commit_strong,
    }
    return {
        **signals,
        "signing_gap": SignalEvidence(
            value=GUARD_VALUE,
            applicable=True,
            evidence=evidence,
        ),
    }
