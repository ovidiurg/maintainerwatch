from __future__ import annotations

import json
from pathlib import Path

from mw import calibration, db


def _write_dataset(path: Path):
    path.mkdir()
    (path / "incidents.jsonl").write_text(json.dumps({
        "incident_id": "test-incident",
        "observation_cutoff": "2026-06-01T00:00:00Z",
        "attack_type": "account_takeover",
    }) + "\n")
    (path / "incident_packages.jsonl").write_text(json.dumps({
        "incident_id": "test-incident",
        "system": "npm",
        "package": "bad-pkg",
        "label": "account_takeover",
    }) + "\n")
    (path / "controls.jsonl").write_text(json.dumps({
        "system": "npm",
        "package": "good-pkg",
        "split": "test",
        "as_of": "2026-01-01T00:00:00Z",
    }) + "\n")


def test_calibration_scores_and_high_band(tmp_path):
    dataset = tmp_path / "dataset"
    _write_dataset(dataset)
    conn = db.connect(tmp_path / "calibration.sqlite")
    db.init_db(conn)
    db.record_signal(
        conn, "npm", "bad-pkg", "publisher_change", 1.0, "high", "{}",
        "0.5.2", "2026-09-01T00:00:00Z",
    )
    db.record_signal(
        conn, "npm", "good-pkg", "publisher_change", 0.0, "low", "{}",
        "0.5.2", "2026-09-01T00:00:00Z",
    )
    conn.commit()

    result = calibration.evaluate_sample(
        conn, dataset, {"publisher_change": 30}, "0.5.2",
        split="test", split_date="2026-01-01",
    )
    assert result["metrics"]["auc"] == 1.0
    assert result["high_band"]["tp"] == 1
    assert result["high_band"]["fp"] == 0
    assert result["high_band"]["precision"] == 1.0
    assert result["high_band"]["recall"] == 1.0
    assert result["score_distribution"]["coverage_mean"] == 1.0


def _th(threshold, precision, recall, fpr):
    return {
        "threshold": threshold, "precision": precision,
        "recall": recall, "false_positive_rate": fpr,
    }


def test_guardrails_detect_test_regression():
    base = {
        "v2_test": {
            "coverage": {"positives": 100, "controls": 100},
            "metrics": {
                "auc": 0.9, "average_precision": 0.9, "brier_score": 0.1,
                "thresholds": [_th(40.0, 0.9, 0.8, 0.01)],
            },
            "high_band": {"precision": 1.0, "recall": 0.1, "false_positive_rate": 0.0},
        }
    }
    bad = {
        "v2_test": {
            "coverage": {"positives": 100, "controls": 100},
            "metrics": {
                "auc": 0.8, "average_precision": 0.8, "brier_score": 0.2,
                "thresholds": [_th(40.0, 0.8, 0.7, 0.2)],
            },
            "high_band": {"precision": 0.8, "recall": 0.1, "false_positive_rate": 0.1},
        }
    }
    checks = calibration.guardrails(base, bad)
    assert checks["passed"] is False
    assert checks["test_auc"]["ok"] is False
    assert checks["test_fpr_40"]["ok"] is False


def test_calibration_history_and_drift(tmp_path):
    result = {
        "baseline_model_version": "0.5.2",
        "candidate_model_version": "0.5.3",
        "passed": True,
        "guardrails": {"passed": True},
        "candidate": {
            "v2_test": {
                "metrics": {
                    "auc": 0.95,
                    "average_precision": 0.96,
                    "brier_score": 0.1,
                    "thresholds": [_th(40.0, 0.97, 0.85, 0.005)],
                },
                "high_band": {"precision": 1.0, "recall": 0.01},
            }
        },
    }
    path = tmp_path / "history.jsonl"
    calibration.append_history(path, result)
    history = calibration.load_history(path)
    assert len(history) == 1
    summary = calibration.drift_summary(history)
    assert summary["runs"] == 1
    assert summary["deltas"]["auc"] == 0.0


def test_propose_weight_candidates_is_bounded_and_unique():
    weights = {"publisher_change": 30, "typosquat": 10, "osv_risk": 0}
    candidates = calibration.propose_weight_candidates(weights, limit=8)
    assert candidates[0] == weights
    assert len(candidates) <= 8
    assert len({tuple(sorted(item.items())) for item in candidates}) == len(candidates)
    assert all(value >= 0 for item in candidates for value in item.values())


def test_bootstrap_compare_reports_ci():
    baseline = {
        "scores": {
            "positive": [90.0, 70.0, 60.0],
            "negative": [10.0, 20.0, 30.0],
            "positive_bands": ["high", "medium", "medium"],
            "negative_bands": ["low", "low", "low"],
        }
    }
    candidate = {
        "scores": {
            "positive": [95.0, 80.0, 70.0],
            "negative": [10.0, 20.0, 30.0],
            "positive_bands": ["high", "medium", "medium"],
            "negative_bands": ["low", "low", "low"],
        }
    }
    result = calibration.bootstrap_compare(baseline, candidate, iterations=100)
    assert result["iterations"] == 100
    assert "ci_95_delta_candidate_minus_baseline" in result
    assert result["recommendation"] in {"apply", "keep-baseline"}


def test_bootstrap_requires_minimum_effect_size():
    baseline = {
        "scores": {
            "positive": [70.0, 60.0, 50.0],
            "negative": [10.0, 20.0, 30.0],
            "positive_bands": ["medium", "medium", "medium"],
            "negative_bands": ["low", "low", "low"],
        }
    }
    candidate = {
        "scores": {
            "positive": [70.1, 60.1, 50.1],
            "negative": [10.0, 20.0, 30.0],
            "positive_bands": ["medium", "medium", "medium"],
            "negative_bands": ["low", "low", "low"],
        }
    }
    result = calibration.bootstrap_compare(
        baseline, candidate, iterations=100, min_auc_gain=0.01,
        min_pr_gain=0.01,
    )
    assert result["checks"]["auc_ci_lower_ge_min_gain"] is False
    assert result["recommendation"] == "keep-baseline"
