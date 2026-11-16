#!/usr/bin/env python3
"""Render calibration history as a small drift report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mw.calibration import drift_summary, load_history

ROOT = Path(__file__).resolve().parents[1]


def markdown(history: list[dict]) -> str:
    summary = drift_summary(history)
    lines = [
        "# Calibration drift",
        "",
        f"Runs: **{summary['runs']}**",
        "",
        "| Generated | Candidate | Passed | v2 test AUC | PR-AUC | Th40 recall | Th40 FPR | High precision |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in history:
        test = item["v2_test"]
        th40 = test["threshold_40"]
        lines.append(
            f"| {item['generated_at']} | {item['candidate_model_version']} | "
            f"{item['passed']} | {test['auc']} | {test['average_precision']} | "
            f"{th40['recall']} | {th40['false_positive_rate']} | "
            f"{test['high_band']['precision']} |"
        )
    if summary["deltas"]:
        lines.extend(["", "## First → last deltas", ""])
        for name, value in summary["deltas"].items():
            lines.append(f"- `{name}`: {value}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history", default="validation/calibration/history.jsonl",
        help="Append-only calibration history.",
    )
    parser.add_argument(
        "--out", default="docs/validation/calibration-drift.md",
        help="Markdown output path.",
    )
    args = parser.parse_args()
    history = load_history(args.history)
    output = markdown(history)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(output, encoding="utf-8")
    print(json.dumps({
        "history": args.history,
        "out": args.out,
        "runs": len(history),
        "deltas": drift_summary(history)["deltas"],
    }, indent=2))


if __name__ == "__main__":
    main()
