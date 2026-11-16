#!/usr/bin/env python3
"""Run a pre-incident replay over the validation case-control sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mw import db, validation
from mw.config import load_config
from mw.evaluate import evaluate

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="validation/v1")
    parser.add_argument("--config", default="config/validation-replay.yaml")
    parser.add_argument("--out", default="data/validation/replay.json")
    args = parser.parse_args()
    cfg = load_config(args.config)
    incidents, packages, controls = validation.load_dataset(ROOT / args.dataset)
    incident_by_id = {item["incident_id"]: item for item in incidents}

    positive_items: dict[tuple[str, str], str] = {}
    for item in packages:
        system = item.get("system")
        name = item.get("package")
        if system not in {"npm", "pypi"} or not name:
            continue
        incident = incident_by_id.get(item.get("incident_id"), {})
        cutoff = incident.get("observation_cutoff") or (
            f"{incident.get('disclosure_date', '')}T00:00:00Z"
        )
        key = (system, name)
        if key not in positive_items or cutoff < positive_items[key]:
            positive_items[key] = cutoff

    benign = [
        (item["system"], item["package"], item.get("as_of") or "2026-01-01T00:00:00Z")
        for item in controls
        if item.get("system") in {"npm", "pypi"}
    ]
    positive = [
        (system, name, cutoff)
        for (system, name), cutoff in sorted(positive_items.items())
    ]

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    positives, negatives, thresholds = evaluate(
        conn, cfg, positive, benign, [25.0, 40.0, 50.0, 60.0]
    )
    conn.close()

    pos_scores = [item.score for item in positives]
    neg_scores = [item.score for item in negatives]
    combined = [(score, 1) for score in pos_scores] + [(score, 0) for score in neg_scores]
    from datetime import datetime, timezone
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": cfg.model_version,
        "dataset": args.dataset,
        "positives_in_dataset": len(positive_items),
        "positives_replayable": len(positives),
        "negatives_replayable": len(negatives),
        "positives_with_applicable_signals": sum(1 for item in positives if item.applicable),
        "auc": validation.auc(pos_scores, neg_scores),
        "precision_at_10": validation.precision_at_k(combined, 10),
        "precision_at_25": validation.precision_at_k(combined, 25),
        "precision_at_50": validation.precision_at_k(combined, 50),
        "thresholds": thresholds,
        "positives": [
            {
                "system": item.system,
                "name": item.name,
                "cutoff": item.cutoff,
                "score": item.score,
                "applicable": item.applicable,
            }
            for item in sorted(positives, key=lambda item: item.score, reverse=True)
        ],
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "positives"}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
