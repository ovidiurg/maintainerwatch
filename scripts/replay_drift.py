#!/usr/bin/env python3
"""Append a replay checkpoint and render a small markdown drift report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _record(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    th40 = next(
        item for item in result["thresholds"] if item["threshold"] == 40.0
    )
    th25 = next(
        item for item in result["thresholds"] if item["threshold"] == 25.0
    )
    return {
        "generated_at": result["generated_at"],
        "model_version": result["model_version"],
        "dataset": result["dataset"],
        "positives": result["positives_replayable"],
        "controls": result["negatives_replayable"],
        "applicable": result["positives_with_applicable_signals"],
        "auc": result["auc"],
        "threshold_25": th25,
        "threshold_40": th40,
    }


def _markdown(history: list[dict]) -> str:
    lines = [
        "# Replay drift",
        "",
        "Pre-incident replay checkpoints. This is a diagnostic track; it is not",
        "used for weight search or tuning.",
        "",
        "| Generated | Model | Dataset | Positives | Applicable | Controls | AUC | Th40 precision | Th40 recall | Th40 FPR |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in history:
        th40 = item["threshold_40"]
        lines.append(
            f"| {item['generated_at']} | {item['model_version']} | "
            f"{item['dataset']} | {item['positives']} | {item['applicable']} | "
            f"{item['controls']} | {item['auc']} | {th40['precision']} | "
            f"{th40['recall']} | {th40['false_positive_rate']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", default="data/validation-v4/replay.json")
    parser.add_argument(
        "--history", default="validation/calibration/replay-history.jsonl"
    )
    parser.add_argument(
        "--out", default="docs/validation/replay-drift.md"
    )
    args = parser.parse_args()
    replay = Path(args.replay)
    record = _record(replay)
    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if history_path.exists():
        history = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if not history or history[-1].get("generated_at") != record["generated_at"]:
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        history.append(record)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_markdown(history), encoding="utf-8")
    print(json.dumps({
        "replay": args.replay,
        "history": args.history,
        "out": args.out,
        "runs": len(history),
        "auc": record["auc"],
    }, indent=2))


if __name__ == "__main__":
    main()
