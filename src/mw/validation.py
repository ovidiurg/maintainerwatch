from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config

ROOT = Path(__file__).resolve().parents[2]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_dataset(dataset_dir: str | Path = ROOT / "validation" / "v1"):
    base = Path(dataset_dir)
    return (
        load_jsonl(base / "incidents.jsonl"),
        load_jsonl(base / "incident_packages.jsonl"),
        load_jsonl(base / "controls.jsonl"),
    )


def precision_at_k(scores: list[tuple[float, int]], k: int) -> float:
    if k <= 0:
        return 0.0
    ordered = sorted(scores, key=lambda item: item[0], reverse=True)[:k]
    if not ordered:
        return 0.0
    return round(sum(label for _, label in ordered) / len(ordered), 3)


def threshold_metrics(pos_scores: list[float], neg_scores: list[float], threshold: float) -> dict:
    tp = sum(1 for score in pos_scores if score >= threshold)
    fn = len(pos_scores) - tp
    fp = sum(1 for score in neg_scores if score >= threshold)
    tn = len(neg_scores) - fp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "false_positive_rate": round(fpr, 3),
    }


def auc(pos_scores: list[float], neg_scores: list[float]) -> float | None:
    if not pos_scores or not neg_scores:
        return None
    combined = sorted(
        [(score, 1) for score in pos_scores] + [(score, 0) for score in neg_scores],
        key=lambda item: item[0],
    )
    # Average ranks for ties.
    ranks: list[float] = [0.0] * len(combined)
    index = 0
    while index < len(combined):
        end = index
        while end + 1 < len(combined) and combined[end + 1][0] == combined[index][0]:
            end += 1
        average_rank = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            ranks[position] = average_rank
        index = end + 1
    positive_rank_sum = sum(
        rank for rank, (_, label) in zip(ranks, combined) if label == 1
    )
    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    value = (positive_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return round(value, 3)


def average_precision(pos_scores: list[float], neg_scores: list[float]) -> float | None:
    if not pos_scores or not neg_scores:
        return None
    combined = sorted(
        [(score, 1) for score in pos_scores] + [(score, 0) for score in neg_scores],
        key=lambda item: item[0], reverse=True,
    )
    total_pos = len(pos_scores)
    hits = 0
    precision_sum = 0.0
    for rank, (_, label) in enumerate(combined, 1):
        if label:
            hits += 1
            precision_sum += hits / rank
    return round(precision_sum / total_pos, 3)


def brier_score(pos_scores: list[float], neg_scores: list[float]) -> float | None:
    if not pos_scores or not neg_scores:
        return None
    errors = [
        (score / 100.0 - label) ** 2
        for score, label in (
            [(score, 1) for score in pos_scores] + [(score, 0) for score in neg_scores]
        )
    ]
    return round(statistics.mean(errors), 4)


def calibration(pos_scores: list[float], neg_scores: list[float], bins: int = 10) -> list[dict]:
    combined = [(score, 1) for score in pos_scores] + [(score, 0) for score in neg_scores]
    out = []
    for index in range(bins):
        lower = index / bins * 100
        upper = (index + 1) / bins * 100
        bucket = [
            (score, label) for score, label in combined
            if (lower <= score < upper) or (index == bins - 1 and score == 100)
        ]
        out.append({
            "bin": f"{lower:.0f}-{upper:.0f}",
            "count": len(bucket),
            "mean_score": round(statistics.mean([score for score, _ in bucket]), 1) if bucket else None,
            "positive_rate": round(statistics.mean([label for _, label in bucket]), 3) if bucket else None,
        })
    return out

def _group_stats(records: list[tuple[float, dict]], key: str) -> dict[str, dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for score, record in records:
        grouped[str(record.get(key) or "unknown")].append(score)
    return {
        name: {
            "count": len(scores),
            "mean_score": round(statistics.mean(scores), 1),
            "median_score": round(statistics.median(scores), 1),
            "high_band": sum(1 for score in scores if score >= 50),
        }
        for name, scores in sorted(grouped.items())
    }


def _temporal_metrics(
    positive_scores: list[tuple[float, dict]],
    neg_values: list[float],
) -> dict[str, dict]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for score, record in positive_scores:
        year = (record.get("cutoff") or "unknown")[:4]
        grouped[year].append(score)
    out = {}
    for year, values in sorted(grouped.items()):
        out[year] = {
            "count": len(values),
            "auc": auc(values, neg_values),
            "average_precision": average_precision(values, neg_values),
            "threshold_40": threshold_metrics(values, neg_values, 40.0),
        }
    return out


def evaluate(
    conn,
    cfg: Config,
    dataset_dir: str | Path = ROOT / "validation" / "v1",
    max_positives: int | None = None,
    max_controls: int | None = None,
    since: str | None = None,
    until: str | None = None,
    split: str | None = None,
    split_date: str | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    dataset_dir = Path(dataset_dir)
    incidents, packages, controls = load_dataset(dataset_dir)
    incident_by_id = {item["incident_id"]: item for item in incidents}

    positives: dict[tuple[str, str], dict] = {}
    for package in packages:
        key = (package.get("system"), package.get("package"))
        incident = incident_by_id.get(package.get("incident_id"), {})
        cutoff = incident.get("observation_cutoff") or ""
        record = {
            "system": package.get("system"),
            "package": package.get("package"),
            "attack_type": package.get("label") or incident.get("attack_type"),
            "priority": incident.get("priority") or "normal",
            "cutoff": cutoff,
            "incident_id": package.get("incident_id"),
            "confidence": package.get("label_confidence"),
        }
        existing = positives.get(key)
        if existing is None or cutoff < (existing.get("cutoff") or "9999"):
            positives[key] = record

    controls_by_key = {
        (control.get("system"), control.get("package")): {
            "system": control.get("system"),
            "package": control.get("package"),
            "split": control.get("split"),
        }
        for control in controls
    }

    scores = {
        (row["system"], row["name"]): float(row["score"])
        for row in conn.execute(
            "SELECT system, name, score FROM scores WHERE model_version=?",
            (cfg.model_version,),
        )
    }

    positive_scores = [
        (scores[key], record) for key, record in positives.items() if key in scores
    ]
    negative_scores = [
        (scores[key], record)
        for key, record in controls_by_key.items()
        if key in scores
        and (split is None or record.get("split") == split)
    ]
    positive_scores.sort(
        key=lambda item: (item[1]["priority"], item[1]["cutoff"]), reverse=True
    )
    if since:
        positive_scores = [
            item for item in positive_scores if (item[1].get("cutoff") or "") >= since
        ]
    if until:
        positive_scores = [
            item for item in positive_scores if (item[1].get("cutoff") or "") <= until
        ]
    if split and split_date:
        if split == "test":
            positive_scores = [
                item for item in positive_scores
                if (item[1].get("cutoff") or "") >= split_date
            ]
        elif split == "train":
            positive_scores = [
                item for item in positive_scores
                if (item[1].get("cutoff") or "") < split_date
            ]
    if max_positives:
        positive_scores = positive_scores[:max_positives]
    if max_controls:
        negative_scores = negative_scores[:max_controls]

    pos_values = [score for score, _ in positive_scores]
    neg_values = [score for score, _ in negative_scores]
    combined = [(score, 1) for score, _ in positive_scores] + [
        (score, 0) for score, _ in negative_scores
    ]
    thresholds = [25.0, 40.0, 50.0, 60.0]

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": cfg.model_version,
        "dataset_dir": str(dataset_dir),
        "split": split,
        "split_date": split_date,
        "coverage": {
            "positives_in_dataset": len(positives),
            "positives_in_db": len(positive_scores),
            "controls_in_dataset": len(controls_by_key),
            "controls_in_db": len(negative_scores),
        },
        "metrics": {
            "precision_at_10": precision_at_k(combined, 10),
            "precision_at_25": precision_at_k(combined, 25),
            "precision_at_50": precision_at_k(combined, 50),
            "precision_at_100": precision_at_k(combined, 100),
            "auc": auc(pos_values, neg_values),
            "average_precision": average_precision(pos_values, neg_values),
            "brier_score": brier_score(pos_values, neg_values),
            "calibration": calibration(pos_values, neg_values),
            "thresholds": [
                threshold_metrics(pos_values, neg_values, threshold)
                for threshold in thresholds
            ],
        },
        "temporal": _temporal_metrics(positive_scores, neg_values),
        "positives_by_attack_type": _group_stats(positive_scores, "attack_type"),
        "positives_by_priority": _group_stats(positive_scores, "priority"),
        "positives_by_system": _group_stats(positive_scores, "system"),
        "negatives_by_system": _group_stats(negative_scores, "system"),
    }

    if write_report:
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "evaluation.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        docs_dir = ROOT / "docs" / "validation"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "evaluation.md").write_text(
            _markdown_report(result), encoding="utf-8"
        )
    return result


def evaluate_ablations(
    conn,
    cfg: Config,
    dataset_dir: str | Path = ROOT / "validation" / "v1",
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Leave-one-signal-out metrics on the validation case-control sample."""
    from .signals import SIGNALS

    dataset_dir = Path(dataset_dir)
    incidents, packages, controls = load_dataset(dataset_dir)
    incident_by_id = {item["incident_id"]: item for item in incidents}
    positives: dict[tuple[str, str], dict] = {}
    for package in packages:
        incident = incident_by_id.get(package.get("incident_id"), {})
        cutoff = incident.get("observation_cutoff") or ""
        key = (package.get("system"), package.get("package"))
        record = {"cutoff": cutoff, "package": package.get("package")}
        if key not in positives or cutoff < (positives[key].get("cutoff") or "9999"):
            positives[key] = record
    controls_by_key = {
        (item.get("system"), item.get("package")): {}
        for item in controls
    }
    scores = {
        (row["system"], row["name"]): float(row["score"])
        for row in conn.execute(
            "SELECT system, name, score FROM scores WHERE model_version=?",
            (cfg.model_version,),
        )
    }
    rows = {}
    for row in conn.execute(
        "SELECT system, name, signal_type, value, band FROM signals "
        "WHERE model_version=?", (cfg.model_version,)
    ):
        rows.setdefault((row["system"], row["name"]), {})[row["signal_type"]] = (
            float(row["value"]), bool(row["band"])
        )
    allowed = set(SIGNALS)
    keys = [key for key in scores if key in positives or key in controls_by_key]
    if since:
        keys = [key for key in keys if key not in positives or (positives[key]["cutoff"] or "") >= since]
    if until:
        keys = [key for key in keys if key not in positives or (positives[key]["cutoff"] or "") <= until]
    pos_keys = [key for key in keys if key in positives]
    neg_keys = [key for key in keys if key in controls_by_key]

    def score(key: str, weights: dict[str, int]) -> float:
        applicable = {
            name: value for name, (value, active) in rows.get(key, {}).items()
            if active and name in weights and name in allowed
        }
        total = sum(weights[name] for name in applicable)
        if not total:
            return 0.0
        return round(100.0 * sum(weights[name] * value for name, value in applicable.items()) / total, 1)

    def metrics(weights: dict[str, int]) -> dict:
        pos = [score(key, weights) for key in pos_keys]
        neg = [score(key, weights) for key in neg_keys]
        return {
            "auc": auc(pos, neg),
            "average_precision": average_precision(pos, neg),
            "threshold_40": threshold_metrics(pos, neg, 40.0),
            "threshold_50": threshold_metrics(pos, neg, 50.0),
        }

    baseline = metrics(cfg.weights)
    ablations = {}
    for name in sorted(SIGNALS):
        if name not in cfg.weights:
            continue
        weights = dict(cfg.weights)
        weights.pop(name, None)
        result = metrics(weights)
        result["delta_auc"] = round(
            (result["auc"] or 0.0) - (baseline["auc"] or 0.0), 3
        )
        ablations[name] = result
    return {
        "model_version": cfg.model_version,
        "baseline": baseline,
        "ablations": ablations,
    }


def _markdown_report(result: dict) -> str:
    coverage = result["coverage"]
    metrics = result["metrics"]
    lines = [
        "# Validation evaluation",
        "",
        f"Generated: {result['generated_at']} · model {result['model_version']}",
        "",
        "> Baseline: current-state scores from the validation ingest, not a "
        "pre-incident replay. Use it to compare model versions on the same sample.",
        "",
        "## Coverage",
        "",
        f"- Positives in dataset: {coverage['positives_in_dataset']}",
        f"- Positives in validation DB: {coverage['positives_in_db']}",
        f"- Controls in dataset: {coverage['controls_in_dataset']}",
        f"- Controls in validation DB: {coverage['controls_in_db']}",
        "",
        "## Ranking metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Precision@10 | {metrics['precision_at_10']} |",
        f"| Precision@25 | {metrics['precision_at_25']} |",
        f"| Precision@50 | {metrics['precision_at_50']} |",
        f"| Precision@100 | {metrics['precision_at_100']} |",
        f"| AUC | {metrics['auc']} |",
        f"| PR-AUC / average precision | {metrics['average_precision']} |",
        f"| Brier score | {metrics['brier_score']} |",
        "",
        "## Threshold metrics",
        "",
        "| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in metrics["thresholds"]:
        lines.append(
            f"| {row['threshold']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{row['tn']} | {row['precision']} | {row['recall']} | "
            f"{row['false_positive_rate']} |"
        )
    lines.extend([
        "", "## Temporal slices", "",
        "| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |",
        "|---|---|---|---|---|",
    ])
    for year, stats in result.get("temporal", {}).items():
        row = stats["threshold_40"]
        lines.append(
            f"| {year} | {stats['count']} | {stats['auc']} | "
            f"{stats['average_precision']} | {row['precision']} / "
            f"{row['recall']} / {row['false_positive_rate']} |"
        )
    lines.extend([
        "", "## Calibration", "",
        "| Score bin | Count | Mean score | Positive rate |",
        "|---|---|---|---|",
    ])
    for row in metrics.get("calibration", []):
        lines.append(
            f"| {row['bin']} | {row['count']} | {row['mean_score']} | "
            f"{row['positive_rate']} |"
        )
    lines.extend(["", "## Positives by attack type", "", "| Type | Count | Mean | Median | High |", "|---|---|---|---|---|"])
    for name, stats in result["positives_by_attack_type"].items():
        lines.append(
            f"| {name} | {stats['count']} | {stats['mean_score']} | "
            f"{stats['median_score']} | {stats['high_band']} |"
        )
    lines.extend([
        "",
        "## Takeover slice",
        "",
        "Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and "
        "xz is in [incident-validation.md](../incident-validation.md).",
        "",
        "## Caveats",
        "",
    ])
    lines.extend([
        "- Current-state scores, not time-aware replay; historical features may leak.",
        "- The validation DB only contains packages that were still ingestible.",
        "- Controls are matched negatives, not guaranteed benign.",
        "- Metrics are case-control, not population estimates.",
    ])
    return "\n".join(lines) + "\n"
