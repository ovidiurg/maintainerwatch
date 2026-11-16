#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f data/validation/maintainerwatch.sqlite ] || [ ! -f data/validation-v2/maintainerwatch.sqlite ]; then
  echo "validation databases missing; build/score them first" >&2
  exit 1
fi

mkdir -p data/calibration
.venv/bin/mw calibrate \
  --candidate config/default.yaml \
  --out data/calibration/latest.json \
  --history validation/calibration/history.jsonl
.venv/bin/python scripts/calibration_drift.py

if [ -f data/validation-v4/maintainerwatch.sqlite ]; then
  .venv/bin/python scripts/validation_replay.py \
    --dataset validation/v4 \
    --config config/validation-v4.yaml \
    --out data/validation-v4/replay.json
  .venv/bin/python scripts/replay_drift.py
fi
