# Validation evaluation

Generated: 2026-11-15T18:38:18.936736+00:00 · model 0.5.2

> Baseline: current-state scores from the validation ingest, not a pre-incident replay. Use it to compare model versions on the same sample.

## Coverage

- Positives in dataset: 29166
- Positives in validation DB: 114
- Controls in dataset: 1148
- Controls in validation DB: 240

## Ranking metrics

| Metric | Value |
|---|---|
| Precision@10 | 1.0 |
| Precision@25 | 1.0 |
| Precision@50 | 1.0 |
| Precision@100 | 0.76 |
| AUC | 0.863 |
| PR-AUC / average precision | 0.839 |
| Brier score | 0.122 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 74 | 20 | 40 | 220 | 0.787 | 0.649 | 0.083 |
| 40.0 | 72 | 1 | 42 | 239 | 0.986 | 0.632 | 0.004 |
| 50.0 | 69 | 0 | 45 | 240 | 1.0 | 0.605 | 0.0 |
| 60.0 | 62 | 0 | 52 | 240 | 1.0 | 0.544 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 1 | 1.0 | 1.0 | 0.5 / 1.0 / 0.004 |
| 2025 | 2 | 0.507 | 0.254 | 0.5 / 0.5 / 0.004 |
| 2026 | 111 | 0.868 | 0.839 | 0.986 / 0.631 / 0.004 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 131 | 6.1 | 0.061 |
| 10-20 | 99 | 14.9 | 0.242 |
| 20-30 | 40 | 23.6 | 0.225 |
| 30-40 | 11 | 33.7 | 0.091 |
| 40-50 | 4 | 46.1 | 0.75 |
| 50-60 | 7 | 52.2 | 1 |
| 60-70 | 12 | 62.7 | 1 |
| 70-80 | 50 | 75.3 | 1 |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 50.6 | 62.9 | 69 |
| typosquat | 2 | 24.7 | 24.7 | 0 |
| worm | 2 | 21.0 | 21.0 | 0 |

## Takeover slice

Pre-incident replay for 9 historical incidents (event-stream, ua-parser-js, colors, node-ipc, eslint-scope, eslint-config-eslint, coa, rc and xz) is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
