# Validation evaluation

Generated: 2026-11-15T23:38:32.126165+00:00 · model 0.5.3

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
| AUC | 0.891 |
| PR-AUC / average precision | 0.878 |
| Brier score | 0.1332 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 372 | 90 | 117 | 918 | 0.805 | 0.761 | 0.089 |
| 40.0 | 328 | 10 | 161 | 998 | 0.97 | 0.671 | 0.01 |
| 50.0 | 327 | 1 | 162 | 1007 | 0.997 | 0.669 | 0.001 |
| 60.0 | 86 | 0 | 403 | 1008 | 1.0 | 0.176 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 10 | 0.645 | 0.361 | 0.333 / 0.5 / 0.01 |
| 2025 | 110 | 0.705 | 0.269 | 0.474 / 0.082 / 0.01 |
| 2026 | 369 | 0.953 | 0.94 | 0.969 / 0.851 / 0.01 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 516 | 6.0 | 0.07 |
| 10-20 | 420 | 14.4 | 0.15 |
| 20-30 | 184 | 24.8 | 0.266 |
| 30-40 | 39 | 33.5 | 0.333 |
| 40-50 | 10 | 43.3 | 0.1 |
| 50-60 | 242 | 51.7 | 0.996 |
| 60-70 | 86 | 66.7 | 1 |
| 70-80 | 0 | None | None |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 455 | 45.0 | 51.7 | 327 |
| typosquat | 3 | 22.2 | 33.3 | 0 |
| worm | 31 | 17.5 | 17.9 | 0 |

## Takeover slice

Pre-incident replay for 9 historical incidents (event-stream, ua-parser-js, colors, node-ipc, eslint-scope, eslint-config-eslint, coa, rc and xz) is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
