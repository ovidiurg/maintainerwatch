# Mature fresh-OSV replay cohort (v4)

Generated 2026-11-16 from fresh OSV `MAL-*` advisories, using the A2 maturity
gate.

## Selection and coverage

| Item | Value |
|---|---:|
| Fresh candidate packages examined | 1,570 present in the expanded DB |
| Positive packages with >=3 pre-cutoff versions | 125 |
| Incidents / packages | 125 / 125 |
| Controls in dataset | 1,148 |
| Replayable positives | 125 |
| Replayable controls | 998 |
| Positives with applicable replay signals | 125 / 125 |
| Positives with pre-cutoff commits | 60 |
| Commit rows backfilled | 9,742 |

Commit history was backfilled for 60 of 125 packages (43 had no repository URL;
22 had a repository but no pre-cutoff commits). Replay therefore combines
release signals with partial commit history.

## Replay result

| Metric | Value |
|---|---:|
| AUC | 0.764 |
| Precision@10 | 0.100 |
| Precision@25 | 0.040 |
| Precision@50 | 0.020 |
| Threshold 25: precision / recall / FPR | 0.280 / 0.536 / 0.172 |
| Threshold 40: precision / recall / FPR | 0.228 / 0.264 / 0.112 |
| Threshold 50: precision / recall / FPR | 0.029 / 0.024 / 0.102 |
| Threshold 60: precision / recall / FPR | 0.010 / 0.008 / 0.097 |

## Verdict

**Usable as a diagnostic replay holdout**, unlike v3: the maturity gate removes
the 326 no-history positives that made v3 invalid. It does **not** demonstrate
current-state model quality and is not yet wired into `mw calibrate`, which
still uses v1/v2. Partial commit coverage (60/125) limits any comparison against
the full-commit v1 replay.

The low precision at high thresholds is a real warning: older controls carry
release/signing signals and the fresh positives are mostly release-anomaly
cases. Do not tune weights on v4; treat it as the next independent replay
checkpoint and report coverage before any metric.
