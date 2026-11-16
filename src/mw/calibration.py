from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, validation
from .config import Config
from .models import SignalEvidence
from .risk import has_high_confidence
from .score import compute_score
from .signals import SIGNALS

DEFAULT_SPLIT_DATE = "2026-01-01"
DEFAULT_THRESHOLDS = [25.0, 40.0, 50.0, 60.0]


@dataclass
class CalibrationSample:
    key: tuple[str, str]
    system: str
    name: str
    label: int
    split: str | None
    cutoff: str
    attack_type: str | None


def _load_signals(conn, model_version: str) -> dict[tuple[str, str], dict[str, dict]]:
    rows = conn.execute(
        "SELECT system, name, signal_type, value, band, evidence_json "
        "FROM signals WHERE model_version=?",
        (model_version,),
    ).fetchall()
    out: dict[tuple[str, str], dict[str, dict]] = {}
    for row in rows:
        out.setdefault((row["system"], row["name"]), {})[row["signal_type"]] = {
            "value": float(row["value"] or 0.0),
            "applicable": bool(row["band"]),
            "evidence": json.loads(row["evidence_json"] or "{}"),
        }
    return out


def _dataset_samples(dataset_dir: str | Path) -> tuple[dict[tuple[str, str], CalibrationSample], dict[tuple[str, str], CalibrationSample]]:
    incidents, packages, controls = validation.load_dataset(dataset_dir)
    incident_by_id = {item["incident_id"]: item for item in incidents}

    positives: dict[tuple[str, str], CalibrationSample] = {}
    for package in packages:
        key = (package.get("system"), package.get("package"))
        incident = incident_by_id.get(package.get("incident_id"), {})
        cutoff = incident.get("observation_cutoff") or ""
        sample = CalibrationSample(
            key=key,
            system=key[0],
            name=key[1],
            label=1,
            split="test" if cutoff >= DEFAULT_SPLIT_DATE else "train",
            cutoff=cutoff,
            attack_type=package.get("label") or incident.get("attack_type"),
        )
        existing = positives.get(key)
        if existing is None or cutoff < (existing.cutoff or "9999"):
            positives[key] = sample

    negatives: dict[tuple[str, str], CalibrationSample] = {}
    for control in controls:
        key = (control.get("system"), control.get("package"))
        negatives[key] = CalibrationSample(
            key=key,
            system=key[0],
            name=key[1],
            label=0,
            split=control.get("split"),
            cutoff=control.get("as_of") or "",
            attack_type=None,
        )
    return positives, negatives


def _score_sample(
    sample: CalibrationSample,
    signals: dict[str, dict],
    weights: dict[str, int],
) -> tuple[float, str, float]:
    evidence = {
        name: SignalEvidence(
            value=value["value"],
            applicable=value["applicable"],
            evidence=value["evidence"],
        )
        for name, value in signals.items()
    }
    score, band, _ = compute_score(evidence, weights, "calibration")
    if band == "high" and not has_high_confidence(signals, sample.system):
        band = "medium"
    total_weight = sum(weights.get(name, 0) for name in SIGNALS)
    applicable_weight = sum(
        weights.get(name, 0)
        for name, value in signals.items()
        if value.get("applicable")
    )
    coverage = applicable_weight / total_weight if total_weight else 0.0
    return score, band, coverage


def evaluate_sample(
    conn,
    dataset_dir: str | Path,
    weights: dict[str, int],
    model_version: str,
    *,
    split: str | None = None,
    split_date: str = DEFAULT_SPLIT_DATE,
    include_scores: bool = False,
) -> dict[str, Any]:
    signals = _load_signals(conn, model_version)
    positives, negatives = _dataset_samples(dataset_dir)

    positive_scores: list[tuple[float, str, float, CalibrationSample]] = []
    negative_scores: list[tuple[float, str, float, CalibrationSample]] = []
    for sample in positives.values():
        if sample.key not in signals:
            continue
        if split == "test" and sample.cutoff < split_date:
            continue
        if split == "train" and sample.cutoff >= split_date:
            continue
        score, band, coverage = _score_sample(sample, signals[sample.key], weights)
        positive_scores.append((score, band, coverage, sample))
    for sample in negatives.values():
        if sample.key not in signals:
            continue
        if split and sample.split != split:
            continue
        score, band, coverage = _score_sample(sample, signals[sample.key], weights)
        negative_scores.append((score, band, coverage, sample))

    pos_values = [item[0] for item in positive_scores]
    neg_values = [item[0] for item in negative_scores]
    combined = [(score, 1) for score in pos_values] + [(score, 0) for score in neg_values]

    high_tp = sum(1 for _, band, _, _ in positive_scores if band == "high")
    high_fn = len(positive_scores) - high_tp
    high_fp = sum(1 for _, band, _, _ in negative_scores if band == "high")
    high_tn = len(negative_scores) - high_fp
    high_precision = high_tp / (high_tp + high_fp) if high_tp + high_fp else 0.0
    high_recall = high_tp / (high_tp + high_fn) if high_tp + high_fn else 0.0
    high_fpr = high_fp / (high_fp + high_tn) if high_fp + high_tn else 0.0

    coverages = [item[2] for item in positive_scores + negative_scores]
    bands: dict[str, int] = {}
    for _, band, _, _ in positive_scores + negative_scores:
        bands[band] = bands.get(band, 0) + 1

    result = {
        "split": split or "all",
        "coverage": {
            "positives": len(positive_scores),
            "controls": len(negative_scores),
        },
        "metrics": {
            "precision_at_10": validation.precision_at_k(combined, 10),
            "precision_at_25": validation.precision_at_k(combined, 25),
            "precision_at_50": validation.precision_at_k(combined, 50),
            "precision_at_100": validation.precision_at_k(combined, 100),
            "auc": validation.auc(pos_values, neg_values),
            "average_precision": validation.average_precision(pos_values, neg_values),
            "brier_score": validation.brier_score(pos_values, neg_values),
            "thresholds": [
                validation.threshold_metrics(pos_values, neg_values, threshold)
                for threshold in DEFAULT_THRESHOLDS
            ],
        },
        "high_band": {
            "tp": high_tp,
            "fp": high_fp,
            "fn": high_fn,
            "tn": high_tn,
            "precision": round(high_precision, 3),
            "recall": round(high_recall, 3),
            "false_positive_rate": round(high_fpr, 3),
        },
        "score_distribution": {
            "mean": round(statistics.mean(pos_values + neg_values), 3)
            if pos_values or neg_values
            else None,
            "median": round(statistics.median(pos_values + neg_values), 3)
            if pos_values or neg_values
            else None,
            "coverage_mean": round(statistics.mean(coverages), 4) if coverages else 0.0,
            "bands": bands,
        },
    }
    if include_scores:
        result["scores"] = {
            "positive": pos_values,
            "negative": neg_values,
            "positive_bands": [item[1] for item in positive_scores],
            "negative_bands": [item[1] for item in negative_scores],
        }
    return result


def _threshold(result: dict[str, Any], value: float) -> dict[str, Any]:
    return next(
        item for item in result["metrics"]["thresholds"] if item["threshold"] == value
    )


def _delta(baseline: float | None, candidate: float | None) -> float | None:
    if baseline is None or candidate is None:
        return None
    return round(candidate - baseline, 4)


def compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    base = baseline["metrics"]
    cand = candidate["metrics"]
    base40 = _threshold(baseline, 40.0)
    cand40 = _threshold(candidate, 40.0)
    base_high = baseline["high_band"]
    cand_high = candidate["high_band"]
    return {
        "auc": _delta(base["auc"], cand["auc"]),
        "average_precision": _delta(base["average_precision"], cand["average_precision"]),
        "brier_score": _delta(base["brier_score"], cand["brier_score"]),
        "threshold_40_precision": _delta(base40["precision"], cand40["precision"]),
        "threshold_40_recall": _delta(base40["recall"], cand40["recall"]),
        "threshold_40_fpr": _delta(base40["false_positive_rate"], cand40["false_positive_rate"]),
        "high_precision": _delta(base_high["precision"], cand_high["precision"]),
        "high_recall": _delta(base_high["recall"], cand_high["recall"]),
        "high_fpr": _delta(base_high["false_positive_rate"], cand_high["false_positive_rate"]),
    }


def guardrails(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    test_base = baseline["v2_test"]
    test_cand = candidate["v2_test"]
    deltas = compare(test_base, test_cand)
    checks = {
        "test_sample": {
            "positives": test_base["coverage"]["positives"],
            "controls": test_base["coverage"]["controls"],
            "ok": test_base["coverage"]["positives"] >= 50
            and test_base["coverage"]["controls"] >= 30,
        },
        "test_auc": {"delta": deltas["auc"], "ok": (deltas["auc"] or 0.0) >= -0.005},
        "test_pr_auc": {
            "delta": deltas["average_precision"],
            "ok": (deltas["average_precision"] or 0.0) >= -0.005,
        },
        "test_recall_40": {
            "delta": deltas["threshold_40_recall"],
            "ok": (deltas["threshold_40_recall"] or 0.0) >= -0.02,
        },
        "test_fpr_40": {
            "delta": deltas["threshold_40_fpr"],
            "ok": (deltas["threshold_40_fpr"] or 0.0) <= 0.02,
        },
        "high_precision": {
            "baseline": test_base["high_band"]["precision"],
            "candidate": test_cand["high_band"]["precision"],
            "delta": deltas["high_precision"],
            "ok": (deltas["high_precision"] or 0.0) >= 0.0,
        },
    }
    checks["passed"] = all(check["ok"] for check in checks.values() if isinstance(check, dict) and "ok" in check)
    return checks


def run(
    baseline_cfg: Config,
    candidate_cfg: Config,
    v1_cfg: Config,
    v2_cfg: Config,
    *,
    split_date: str = DEFAULT_SPLIT_DATE,
) -> dict[str, Any]:
    results: dict[str, Any] = {"baseline": {}, "candidate": {}}
    for label, cfg in (("v1", v1_cfg), ("v2_full", v2_cfg), ("v2_test", v2_cfg)):
        conn = db.connect(cfg.db_path)
        db.init_db(conn)
        split = "test" if label == "v2_test" else None
        results["baseline"][label] = evaluate_sample(
            conn, "validation/v1", baseline_cfg.weights, cfg.model_version,
            split=split, split_date=split_date,
        )
        results["candidate"][label] = evaluate_sample(
            conn, "validation/v1", candidate_cfg.weights, cfg.model_version,
            split=split, split_date=split_date,
        )
        conn.close()
    results["deltas"] = {
        label: compare(results["baseline"][label], results["candidate"][label])
        for label in results["baseline"]
    }
    results["guardrails"] = guardrails(results["baseline"], results["candidate"])
    results["passed"] = results["guardrails"]["passed"]
    results["baseline_model_version"] = baseline_cfg.model_version
    results["candidate_model_version"] = candidate_cfg.model_version
    results["candidate_weights"] = candidate_cfg.weights
    return results


def history_entry(result: dict[str, Any]) -> dict[str, Any]:
    test = result["candidate"]["v2_test"]
    th40 = _threshold(test, 40.0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_model_version": result["baseline_model_version"],
        "candidate_model_version": result["candidate_model_version"],
        "passed": result["passed"],
        "guardrails": result["guardrails"],
        "v2_test": {
            "auc": test["metrics"]["auc"],
            "average_precision": test["metrics"]["average_precision"],
            "brier_score": test["metrics"]["brier_score"],
            "threshold_40": th40,
            "high_band": test["high_band"],
        },
    }


def append_history(path: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = history_entry(result)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def load_history(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def drift_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"runs": 0, "first": None, "last": None, "deltas": {}}
    first = history[0]["v2_test"]
    last = history[-1]["v2_test"]
    deltas = {
        "auc": _delta(first["auc"], last["auc"]),
        "average_precision": _delta(
            first["average_precision"], last["average_precision"]
        ),
        "brier_score": _delta(first["brier_score"], last["brier_score"]),
        "threshold_40_recall": _delta(
            first["threshold_40"]["recall"], last["threshold_40"]["recall"]
        ),
        "threshold_40_fpr": _delta(
            first["threshold_40"]["false_positive_rate"],
            last["threshold_40"]["false_positive_rate"],
        ),
        "high_precision": _delta(
            first["high_band"]["precision"], last["high_band"]["precision"]
        ),
        "high_recall": _delta(
            first["high_band"]["recall"], last["high_band"]["recall"]
        ),
    }
    return {
        "runs": len(history),
        "first": history[0]["generated_at"],
        "last": history[-1]["generated_at"],
        "deltas": deltas,
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _bootstrap_metrics(
    pos_values: list[float],
    neg_values: list[float],
    pos_bands: list[str],
    neg_bands: list[str],
) -> dict[str, float]:
    th40 = validation.threshold_metrics(pos_values, neg_values, 40.0)
    high_tp = sum(1 for band in pos_bands if band == "high")
    high_fp = sum(1 for band in neg_bands if band == "high")
    high_precision = high_tp / (high_tp + high_fp) if high_tp + high_fp else 0.0
    return {
        "auc": validation.auc(pos_values, neg_values) or 0.0,
        "average_precision": validation.average_precision(pos_values, neg_values),
        "brier_score": validation.brier_score(pos_values, neg_values),
        "threshold_40_precision": th40["precision"],
        "threshold_40_recall": th40["recall"],
        "threshold_40_fpr": th40["false_positive_rate"],
        "high_precision": round(high_precision, 3),
    }


def bootstrap_compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    import random

    base = baseline["scores"]
    cand = candidate["scores"]
    if not base["positive"] or not base["negative"]:
        return {"iterations": 0, "error": "bootstrap needs positives and controls"}
    rng = random.Random(seed)
    names = (
        "auc", "average_precision", "brier_score",
        "threshold_40_precision", "threshold_40_recall",
        "threshold_40_fpr", "high_precision",
    )
    deltas: dict[str, list[float]] = {name: [] for name in names}
    for _ in range(iterations):
        pos_idx = [rng.randrange(len(base["positive"])) for _ in base["positive"]]
        neg_idx = [rng.randrange(len(base["negative"])) for _ in base["negative"]]
        b_pos = [base["positive"][i] for i in pos_idx]
        b_neg = [base["negative"][i] for i in neg_idx]
        c_pos = [cand["positive"][i] for i in pos_idx]
        c_neg = [cand["negative"][i] for i in neg_idx]
        b = _bootstrap_metrics(
            b_pos, b_neg,
            [base["positive_bands"][i] for i in pos_idx],
            [base["negative_bands"][i] for i in neg_idx],
        )
        c = _bootstrap_metrics(
            c_pos, c_neg,
            [cand["positive_bands"][i] for i in pos_idx],
            [cand["negative_bands"][i] for i in neg_idx],
        )
        for name in names:
            deltas[name].append(c[name] - b[name])
    ci = {
        name: [round(_percentile(values, 0.025), 4), round(_percentile(values, 0.975), 4)]
        for name, values in deltas.items()
    }
    win = {
        name: round(sum(1 for value in values if value > 0) / iterations, 3)
        for name, values in deltas.items()
    }
    stable_gain = ci["auc"][0] > 0 and ci["average_precision"][0] > 0
    fpr_ok = ci["threshold_40_fpr"][1] <= 0.02
    high_precision_ok = ci["high_precision"][0] >= -0.02
    return {
        "iterations": iterations,
        "seed": seed,
        "ci_95_delta_candidate_minus_baseline": ci,
        "candidate_wins_fraction": win,
        "recommendation": "apply" if stable_gain and fpr_ok and high_precision_ok else "keep-baseline",
        "checks": {
            "auc_ci_above_zero": ci["auc"][0] > 0,
            "pr_auc_ci_above_zero": ci["average_precision"][0] > 0,
            "fpr_ci_upper_le_0.02": fpr_ok,
            "high_precision_ci_lower_ge_minus_0.02": high_precision_ok,
        },
    }


def propose_weight_candidates(
    weights: dict[str, int],
    *,
    fractions: tuple[float, ...] = (0.75, 1.25, 0.5, 1.5),
    limit: int = 80,
) -> list[dict[str, int]]:
    """Return unique nearby weight sets; the baseline is always first."""
    baseline = {name: int(value) for name, value in weights.items()}
    candidates: list[dict[str, int]] = [baseline]
    seen = {tuple(sorted(baseline.items()))}
    for name, value in sorted(weights.items()):
        if value <= 0:
            continue
        for fraction in fractions:
            candidate = dict(baseline)
            candidate[name] = max(0, int(round(value * fraction)))
            key = tuple(sorted(candidate.items()))
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _selection_score(v1: dict[str, Any], v2_train: dict[str, Any]) -> tuple[float, float, float]:
    def value(result: dict[str, Any], name: str) -> float:
        return float(result["metrics"].get(name) or 0.0)
    return (
        round((value(v1, "average_precision") + value(v2_train, "average_precision")) / 2, 4),
        round((value(v1, "auc") + value(v2_train, "auc")) / 2, 4),
        round((_threshold(v1, 40.0)["recall"] + _threshold(v2_train, 40.0)["recall"]) / 2, 4),
    )


def search(
    baseline_cfg: Config,
    v1_cfg: Config,
    v2_cfg: Config,
    *,
    start_weights: dict[str, int] | None = None,
    split_date: str = DEFAULT_SPLIT_DATE,
    max_candidates: int = 80,
    bootstrap: int = 0,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    """Search nearby weights on v1 + v2 train only; v2 test is held out."""
    weights = dict(start_weights or baseline_cfg.weights)
    candidates = propose_weight_candidates(weights, limit=max_candidates)
    conn1 = db.connect(v1_cfg.db_path)
    db.init_db(conn1)
    conn2 = db.connect(v2_cfg.db_path)
    db.init_db(conn2)
    baseline_v1 = evaluate_sample(
        conn1, "validation/v1", baseline_cfg.weights, v1_cfg.model_version,
        split_date=split_date,
    )
    baseline_train = evaluate_sample(
        conn2, "validation/v1", baseline_cfg.weights, v2_cfg.model_version,
        split="train", split_date=split_date,
    )
    baseline_test = evaluate_sample(
        conn2, "validation/v1", baseline_cfg.weights, v2_cfg.model_version,
        split="test", split_date=split_date, include_scores=bool(bootstrap),
    )
    ranked = []
    for candidate_weights in candidates:
        v1 = evaluate_sample(
            conn1, "validation/v1", candidate_weights, v1_cfg.model_version,
            split_date=split_date,
        )
        train = evaluate_sample(
            conn2, "validation/v1", candidate_weights, v2_cfg.model_version,
            split="train", split_date=split_date,
        )
        ranked.append({
            "weights": candidate_weights,
            "selection_score": _selection_score(v1, train),
            "v1": v1,
            "v2_train": train,
        })
    ranked.sort(key=lambda item: item["selection_score"], reverse=True)
    selected = ranked[0]
    selected_test = evaluate_sample(
        conn2, "validation/v1", selected["weights"], v2_cfg.model_version,
        split="test", split_date=split_date, include_scores=bool(bootstrap),
    )
    conn1.close()
    conn2.close()
    baseline = {
        "v2_test": baseline_test,
        "v1": baseline_v1,
        "v2_train": baseline_train,
    }
    candidate = {
        "v2_test": selected_test,
        "v1": selected["v1"],
        "v2_train": selected["v2_train"],
    }
    checks = guardrails(baseline, candidate)
    bootstrap_result = (
        bootstrap_compare(
            baseline_test, selected_test,
            iterations=bootstrap, seed=bootstrap_seed,
        )
        if bootstrap else None
    )
    return {
        "bootstrap": bootstrap_result,
        "search": {
            "candidates": len(ranked),
            "selection": "v1 + v2 train PR-AUC/AUC/recall; v2 test held out",
            "selected_weights": selected["weights"],
            "selected_score": selected["selection_score"],
            "top": ranked[:10],
        },
        "baseline": baseline,
        "candidate": candidate,
        "deltas": {
            "v1": compare(baseline_v1, selected["v1"]),
            "v2_train": compare(baseline_train, selected["v2_train"]),
            "v2_test": compare(baseline_test, selected_test),
        },
        "guardrails": checks,
        "passed": checks["passed"],
        "baseline_model_version": baseline_cfg.model_version,
        "candidate_model_version": v1_cfg.model_version,
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Calibration report",
        "",
        f"Baseline model: `{result['baseline_model_version']}`  ",
        f"Candidate model: `{result['candidate_model_version']}`  ",
        f"Guardrails: **{'PASS' if result['passed'] else 'FAIL'}**",
        "",
        "| Sample | AUC | PR-AUC | Th40 precision | Th40 recall | Th40 FPR | High precision | High recall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("v1", "v2_full", "v2_test"):
        for side in ("baseline", "candidate"):
            item = result[side][label]
            th40 = _threshold(item, 40.0)
            high = item["high_band"]
            lines.append(
                f"| {label} {side} | {item['metrics']['auc']} | "
                f"{item['metrics']['average_precision']} | "
                f"{th40['precision']} | {th40['recall']} | "
                f"{th40['false_positive_rate']} | {high['precision']} | "
                f"{high['recall']} |"
            )
    lines.extend(["", "## Guardrails", ""])
    for name, check in result["guardrails"].items():
        if name == "passed":
            continue
        lines.append(f"- **{name}**: {json.dumps(check, sort_keys=True)}")
    return "\n".join(lines) + "\n"
