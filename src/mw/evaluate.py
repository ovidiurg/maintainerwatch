from __future__ import annotations

from dataclasses import dataclass

from . import db
from .config import Config
from .models import SignalEvidence
from .resolve import identity_map
from .signals import compute_all
from .signals import package_age
from .signals.base import Context
from .signals.typosquat import TARGET_MIN_DOWNLOADS

REPLAY_SIGNALS = [
    "publisher_change",
    "release_anomaly",
    "signing_gap",
    "commit_anomaly",
    "install_script",
    "package_age",
]


def replay_score(signals: dict[str, SignalEvidence], weights: dict[str, int]) -> float:
    available = {
        name: sig
        for name, sig in signals.items()
        if name in REPLAY_SIGNALS and name in weights and sig.applicable
    }
    total = sum(weights[name] for name in available)
    if not total:
        return 0.0
    return round(
        100.0 * sum(weights[name] * sig.value for name, sig in available.items()) / total,
        1,
    )


@dataclass
class ReplayResult:
    system: str
    name: str
    cutoff: str
    score: float
    values: dict[str, float]
    applicable: list[str]


def replay(
    conn,
    cfg: Config,
    system: str,
    name: str,
    cutoff: str,
    top_names: list[str] | None = None,
) -> ReplayResult | None:
    pkg = db.get_package(conn, system, name)
    if pkg is None:
        return None

    ctx = Context(
        conn=conn,
        system=system,
        name=name,
        downloads_weekly=int(pkg["downloads_weekly"] or 0),
        top_names=top_names or db.top_names(
            conn, system, 5000, min_downloads=TARGET_MIN_DOWNLOADS
        ),
        identity_mapping=identity_map(conn, system, name, cfg.min_identity_confidence),
        license=pkg["license"],
        as_of=cutoff,
        automation_identities=cfg.automation_identities,
        automation_patterns=cfg.automation_patterns,
    )
    signals = compute_all(ctx)
    signals["package_age"] = package_age.compute(ctx)
    return ReplayResult(
        system=system,
        name=name,
        cutoff=cutoff,
        score=replay_score(signals, cfg.weights),
        values={k: round(signals[k].value, 3) for k in REPLAY_SIGNALS},
        applicable=[k for k in REPLAY_SIGNALS if signals[k].applicable],
    )


def metrics_at(pos_scores: list[float], neg_scores: list[float], threshold: float) -> dict:
    true_pos = sum(1 for score in pos_scores if score >= threshold)
    false_neg = len(pos_scores) - true_pos
    false_pos = sum(1 for score in neg_scores if score >= threshold)
    true_neg = len(neg_scores) - false_pos

    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 0.0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 0.0
    fpr = false_pos / (false_pos + true_neg) if (false_pos + true_neg) else 0.0

    return {
        "threshold": threshold,
        "tp": true_pos,
        "fp": false_pos,
        "fn": false_neg,
        "tn": true_neg,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "false_positive_rate": round(fpr, 3),
    }


def evaluate(
    conn,
    cfg: Config,
    incidents: list[tuple[str, str, str]],
    benign: list[tuple[str, str, str]],
    thresholds: list[float],
) -> tuple[list[ReplayResult], list[ReplayResult], list[dict]]:
    top_cache: dict[str, list[str]] = {}

    def run(item: tuple[str, str, str]) -> ReplayResult | None:
        system, name, cutoff = item
        if system not in top_cache:
            top_cache[system] = db.top_names(
                conn, system, 5000, min_downloads=TARGET_MIN_DOWNLOADS
            )
        return replay(conn, cfg, system, name, cutoff, top_cache[system])

    positives = [r for r in (run(item) for item in incidents) if r is not None]
    negatives = [r for r in (run(item) for item in benign) if r is not None]
    pos_scores = [r.score for r in positives]
    neg_scores = [r.score for r in negatives]
    metrics = [metrics_at(pos_scores, neg_scores, t) for t in thresholds]
    return positives, negatives, metrics
