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
| Positives with pre-cutoff commits | 0 |

Commit history was not fetched for the expanded cohort, so
`commit_anomaly` is absent and the replay is release-metadata only.

## Replay result

| Metric | Value |
|---|---:|
| AUC | 0.767 |
| Precision@10 | 0.100 |
| Precision@25 | 0.040 |
| Precision@50 | 0.020 |
| Threshold 25: precision / recall / FPR | 0.283 / 0.544 / 0.172 |
| Threshold 40: precision / recall / FPR | 0.233 / 0.272 / 0.112 |
| Threshold 50: precision / recall / FPR | 0.029 / 0.024 / 0.102 |
| Threshold 60: precision / recall / FPR | 0.020 / 0.016 / 0.097 |

## Verdict

**Usable as a diagnostic replay holdout**, unlike v3: the maturity gate removes
the 326 no-history positives that made v3 invalid. It does **not** demonstrate
current-state model quality and is not yet wired into `mw calibrate`, which
still uses v1/v2.

The low precision at high thresholds is a real warning: older controls carry
release/signing signals and the fresh positives are mostly release-anomaly
cases. Do not tune weights on v4; treat it as the next independent replay
checkpoint and report coverage before any metric.
