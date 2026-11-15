# Feedback and calibration loop

`mw calibrate` compares a candidate weight configuration with the current
baseline on the temporal validation samples. It does not retrain or silently
change the model.

## What it evaluates

- v1 case-control sample
- v2 full sample
- v2 temporal test slice (`>= 2026-01-01`)
- AUC, PR-AUC, Brier score and precision/recall/FPR at thresholds 25/40/50/60
- high-band precision, recall and false-positive rate
- evidence coverage and score distribution

The candidate weights are applied to the signal values already stored in the
validation databases, so the command is fast and does not use post-cutoff
labels to recompute candidate scores.

## Workflow

```bash
# Start from the current model.
cp config/default.yaml config/calibration-candidate.yaml
# Edit only weights/model_version in the candidate file.

mw calibrate \
  --candidate config/calibration-candidate.yaml \
  --fail-on-regression

cat data/calibration.md
```

Outputs are local and git-ignored:

- `data/calibration.json`
- `data/calibration.md`
- `data/calibration/history.jsonl`
- `data/calibration/drift.md` (via `python scripts/calibration_drift.py`)

The history is append-only. Inspect metric drift with:

```bash
python scripts/calibration_drift.py
cat data/calibration/drift.md
```

## Guardrails

The candidate fails when the v2 test slice:

- has fewer than 50 positives or 30 controls;
- loses more than 0.005 AUC or PR-AUC;
- loses more than 0.02 threshold-40 recall;
- increases threshold-40 FPR by more than 0.02;
- reduces high-band precision.

These are minimum guardrails, not a replacement for human review. Do not tune
on the test slice; use v1 and the v2 train slice for exploration, then treat the
test slice as a holdout.

## Weekly loop

1. Add new labels from OSV MAL/advisories, documented incidents and
   false-positive reports to the validation datasets.
2. Keep the temporal holdout frozen.
3. Run `mw calibrate` plus the incident replay (`python
   scripts/incident_check.py`).
4. Review deltas and failure cases; run `mw evaluate-ablations` for signal
   attribution.
5. Bump `model_version` only after the candidate passes; record the decision in
   the model changelog and keep the previous version in the scores table.

The initial loop is intentionally manual. Automated label intake and a drift
dashboard remain follow-up work.
