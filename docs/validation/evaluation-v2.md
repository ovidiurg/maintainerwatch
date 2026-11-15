# Validation evaluation

Generated: 2026-11-14T23:52:56.707364+00:00 · model 0.5.1

> Baseline: current-state scores from the validation ingest, not a pre-incident replay. Use it to compare model versions on the same sample.

## Coverage

- Positives in dataset: 29166
- Positives in validation DB: 489
- Controls in dataset: 1148
- Controls in validation DB: 1008

## Ranking metrics

| Metric | Value |
|---|---|
| Precision@10 | 1.0 |
| Precision@25 | 1.0 |
| Precision@50 | 1.0 |
| Precision@100 | 0.99 |
| AUC | 0.879 |
| PR-AUC / average precision | 0.863 |
| Brier score | 0.1452 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 348 | 85 | 141 | 923 | 0.804 | 0.712 | 0.084 |
| 40.0 | 328 | 9 | 161 | 999 | 0.973 | 0.671 | 0.009 |
| 50.0 | 87 | 1 | 402 | 1007 | 0.989 | 0.178 | 0.001 |
| 60.0 | 86 | 0 | 403 | 1008 | 1.0 | 0.176 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 10 | 0.652 | 0.361 | 0.357 / 0.5 / 0.009 |
| 2025 | 110 | 0.667 | 0.228 | 0.5 / 0.082 / 0.009 |
| 2026 | 369 | 0.948 | 0.932 | 0.972 / 0.851 / 0.009 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 552 | 5.9 | 0.067 |
| 10-20 | 409 | 14.3 | 0.178 |
| 20-30 | 171 | 24.6 | 0.281 |
| 30-40 | 28 | 33.7 | 0.107 |
| 40-50 | 249 | 47.8 | 0.968 |
| 50-60 | 2 | 53.5 | 0.5 |
| 60-70 | 86 | 60.1 | 1 |
| 70-80 | 0 | None | None |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 455 | 41.1 | 48.0 | 87 |
| typosquat | 3 | 18.2 | 27.3 | 0 |
| worm | 31 | 15.8 | 13.8 | 0 |

## Takeover slice

Pre-incident replay for 9 historical incidents (event-stream, ua-parser-js, colors, node-ipc, eslint-scope, eslint-config-eslint, coa, rc and xz) is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
