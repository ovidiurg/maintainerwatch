# Calibration history

This directory is the persistent, append-only calibration log.

- `history.jsonl`: one record per baseline/candidate evaluation.
- `holdout.json`: the v2 temporal test policy and usage state.
- `replay-history.jsonl` and `docs/validation/replay-drift.md`: the separate
  replay diagnostic track (currently v4); this is not used for weight search.

Anti-overfitting rules:

- v2 test is the final holdout, not a tuning set.
- Search selection uses v1 + v2 train only.
- `validation/v3` is a fresh-OSV **diagnostic cohort**, not a cleared holdout;
  it is rejected for tuning because 326 of 381 positives have no pre-cutoff
  history.
- `validation/v4` is the mature-subset replay diagnostic (125 positives, all
  applicable, AUC 0.764). It is not yet wired into `mw calibrate`; do not tune
  on it.
- `validation/v5` is a fresh current-state diagnostic (108 positives, AUC 0.931,
  threshold-40 recall 0.269). It is not yet wired into `mw calibrate`; do not
  tune on it.
- Do not repeatedly search the same test slice. If a new candidate is needed,
  prefer a new/rolling holdout and freeze the current one.
- Require a minimum lower-CI gain: AUC >= 0.005 and PR-AUC >= 0.005.
- Do not apply small point estimates with confidence intervals that include
  zero or negligible effects.

The loop script (`scripts/calibration_loop.sh`) only refreshes the baseline
history and drift report. It deliberately does not run a new search.
