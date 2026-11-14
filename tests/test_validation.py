from __future__ import annotations

import json

from mw import db, validation
from mw.config import load_config


def test_precision_at_k():
    scores = [(90.0, 1), (70.0, 1), (60.0, 0), (10.0, 0)]
    assert validation.precision_at_k(scores, 2) == 1.0
    assert validation.precision_at_k(scores, 4) == 0.5
    assert validation.precision_at_k(scores, 0) == 0.0


def test_threshold_metrics():
    metrics = validation.threshold_metrics([80.0, 60.0], [10.0, 20.0], 50.0)
    assert metrics["tp"] == 2
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0
    assert metrics["tn"] == 2
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["false_positive_rate"] == 0.0


def test_auc():
    assert validation.auc([80.0, 60.0], [10.0, 20.0]) == 1.0
    assert validation.auc([10.0, 20.0], [80.0, 60.0]) == 0.0
    assert validation.auc([], [10.0]) is None


def test_average_precision_brier_and_calibration():
    assert validation.average_precision([80.0, 60.0], [10.0, 20.0]) == 1.0
    assert validation.average_precision([10.0, 20.0], [80.0, 60.0]) == 0.417
    assert validation.brier_score([100.0], [0.0]) == 0.0
    bins = validation.calibration([80.0], [10.0], bins=10)
    assert len(bins) == 10
    assert sum(item["count"] for item in bins) == 2


def test_committed_dataset_counts_match_manifest():
    incidents, packages, controls = validation.load_dataset()
    manifest = json.loads(
        (validation.ROOT / "validation" / "v1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(incidents) == manifest["counts"]["incidents"]
    assert len(packages) == manifest["counts"]["incident_packages"]
    assert len(controls) == manifest["counts"]["controls"]


def test_evaluate_synthetic(tmp_path):
    dataset = tmp_path / "v1"
    dataset.mkdir()
    (dataset / "incidents.jsonl").write_text(
        json.dumps({
            "incident_id": "inc1",
            "attack_type": "typosquat",
            "observation_cutoff": "2024-01-01T00:00:00Z",
            "disclosure_date": "2024-01-02",
            "priority": "high",
        }) + "\n",
        encoding="utf-8",
    )
    (dataset / "incident_packages.jsonl").write_text(
        "\n".join(
            json.dumps({"incident_id": "inc1", "system": "npm", "package": name,
                        "label": "typosquat", "label_confidence": "high"})
            for name in ("bad-a", "bad-b")
        ) + "\n",
        encoding="utf-8",
    )
    (dataset / "controls.jsonl").write_text(
        "\n".join(
            json.dumps({"system": "npm", "package": name, "label": "benign"})
            for name in ("good-a", "good-b")
        ) + "\n",
        encoding="utf-8",
    )

    cfg = load_config()
    conn = db.connect(":memory:")
    db.init_db(conn)
    for name, score in (("bad-a", 70.0), ("bad-b", 30.0), ("good-a", 20.0), ("good-b", 10.0)):
        db.record_score(conn, "npm", name, score, "medium", cfg.model_version, "hash", "2026-01-01")
    db.record_signal(conn, "npm", "bad-a", "publisher_change", 1.0, "high", "{}", cfg.model_version, "2026-01-01")
    db.record_signal(conn, "npm", "bad-b", "publisher_change", 0.0, "low", "{}", cfg.model_version, "2026-01-01")
    conn.commit()

    result = validation.evaluate(conn, cfg, dataset, write_report=False)

    assert result["coverage"]["positives_in_db"] == 2
    assert result["coverage"]["controls_in_db"] == 2
    assert result["metrics"]["precision_at_10"] == 0.5
    assert result["metrics"]["auc"] == 1.0
    assert result["metrics"]["average_precision"] == 1.0
    assert result["metrics"]["brier_score"] is not None
    assert result["temporal"]["2024"]["count"] == 2

    ablations = validation.evaluate_ablations(conn, cfg, dataset)
    assert "baseline" in ablations
    assert "publisher_change" in ablations["ablations"]
    assert "delta_auc" in ablations["ablations"]["publisher_change"]

    filtered = validation.evaluate(
        conn, cfg, dataset, since="2025-01-01T00:00:00Z", write_report=False,
    )
    assert filtered["coverage"]["positives_in_db"] == 0
    conn.close()
