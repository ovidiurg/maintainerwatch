from __future__ import annotations

from typing import Any

from .impact import impact_tier

HIGH_CONFIDENCE_SIGNALS = {
    "publisher_change", "commit_anomaly", "osv_risk", "depsdev_findings",
    "install_script", "maintainer_continuity",
}


def has_high_confidence(signals: dict, system: str | None = None) -> bool:
    for name in HIGH_CONFIDENCE_SIGNALS:
        signal = signals.get(name)
        if signal is None:
            continue
        value = (
            signal.get("value", 0)
            if isinstance(signal, dict)
            else getattr(signal, "value", 0)
        )
        if (
            system in {"github", "maven"}
            and name in {"publisher_change", "commit_anomaly"}
        ):
            # Release authors and GitHub commit samples are noisy on these
            # ecosystems; require an advisory/content signal for high confidence.
            continue
        if name == "commit_anomaly":
            evidence = (
                signal.get("evidence") or {}
                if isinstance(signal, dict)
                else getattr(signal, "evidence", {}) or {}
            )
            if value >= 0.5 and (
                float(evidence.get("new_author_share") or 0.0) >= 0.5
                or float(evidence.get("new_author_value") or 0.0) >= 0.5
            ):
                return True
            continue
        if value >= 0.5:
            return True
    return False

def _value(signals: dict[str, dict[str, Any]], name: str) -> float:
    return float(signals.get(name, {}).get("value") or 0.0)


def _evidence(signals: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return signals.get(name, {}).get("evidence") or {}


def describe_risk(signals: dict[str, dict[str, Any]]) -> tuple[str, str, str]:
    """Return a short risk type, description and next investigation step."""
    publisher = _value(signals, "publisher_change")
    commit = _value(signals, "commit_anomaly")
    install = _value(signals, "install_script")
    typosquat = _value(signals, "typosquat")
    release = _value(signals, "release_anomaly")
    signing = _value(signals, "signing_gap")
    bus = _value(signals, "bus_factor")
    dependency = _value(signals, "dependency_risk")
    license_risk = _value(signals, "license_inconsistency")

    if publisher >= 0.5 or commit >= 0.5:
        if publisher >= 0.5 and int(_evidence(signals, "publisher_change").get("n_legitimate", 0)) == 0:
            return (
                "Maintainer takeover",
                "Publisher changed without a legitimate handover context.",
                "Review the new publisher and recent releases; verify the handover out-of-band.",
            )
        return (
            "Maintainer turnover",
            "Publisher or commit authorship changed recently.",
            "Confirm the handover in project channels and review recent release diffs.",
        )

    if install >= 0.8:
        patterns = ", ".join(_evidence(signals, "install_script").get("high_risk_patterns") or [])
        return (
            "Suspicious install script",
            f"Install script matched: {patterns or 'download/execution patterns'}.",
            "Inspect the install script and tarball; block the version if confirmed.",
        )

    if typosquat >= 0.8:
        nearest = _evidence(signals, "typosquat").get("nearest") or "a popular package"
        return (
            "Possible typosquat",
            f"Name is close to {nearest}.",
            "Compare with the legitimate package and check publisher and repository.",
        )

    if release >= 0.5 and bus >= 0.7:
        ev = _evidence(signals, "release_anomaly")
        return (
            "Dormant, concentrated project",
            f"No release for {ev.get('last_gap_days', '?')} days; top author "
            f"{round(100 * ev.get('top_author_share', bus))}% of commits.",
            "Check recent commits and maintainer activity; confirm the project is maintained.",
        )

    if release >= 0.5:
        ev = _evidence(signals, "release_anomaly")
        return (
            "Release anomaly",
            f"Last gap {ev.get('last_gap_days', '?')} days vs median "
            f"{ev.get('median_gap_days', '?')} days.",
            "Review the last release diff and notes; check publisher and commit history.",
        )

    if signing >= 0.5:
        ev = _evidence(signals, "signing_gap")
        if ev.get("baseline_unsigned"):
            return (
                "Missing provenance",
                "No provenance or signatures in package history.",
                "Verify release signatures/provenance and publisher identity.",
            )
        return (
            "Unsigned releases",
            f"Recent signing/provenance coverage is {ev.get('coverage', '?')}.",
            "Check why recent releases lost signing/provenance; review CI configuration.",
        )

    if bus >= 0.7:
        ev = _evidence(signals, "bus_factor")
        return (
            "Maintainer concentration",
            f"Top author contributes {round(100 * ev.get('top_author_share', bus))}% of commits.",
            "Check contributor activity and continuity; look for recent handovers.",
        )

    if dependency >= 0.5:
        ev = _evidence(signals, "dependency_risk")
        return (
            "High-impact dependency",
            f"{ev.get('fan_in_transitive', '?')} transitive dependents.",
            "Assess downstream impact and monitor maintainer and release changes.",
        )

    if license_risk >= 0.5:
        return (
            "Metadata hygiene",
            "Missing, unknown or inconsistent license metadata.",
            "Verify license metadata against the project repository.",
        )

    return (
        "General risk",
        "Score driven by a mix of weaker signals.",
        "Review the top contributing signals and package context.",
    )
