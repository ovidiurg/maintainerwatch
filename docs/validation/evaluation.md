# Validation evaluation

Generated: 2026-11-15T23:38:10.712631+00:00 · model 0.5.3

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
| Precision@100 | 0.8 |
| AUC | 0.875 |
| PR-AUC / average precision | 0.855 |
| Brier score | 0.1164 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 80 | 20 | 34 | 220 | 0.8 | 0.702 | 0.083 |
| 40.0 | 72 | 2 | 42 | 238 | 0.973 | 0.632 | 0.008 |
| 50.0 | 71 | 1 | 43 | 239 | 0.986 | 0.623 | 0.004 |
| 60.0 | 62 | 0 | 52 | 240 | 1.0 | 0.544 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 1 | 1.0 | 1.0 | 0.333 / 1.0 / 0.008 |
| 2025 | 2 | 0.505 | 0.171 | 0.333 / 0.5 / 0.008 |
| 2026 | 111 | 0.88 | 0.856 | 0.972 / 0.631 / 0.008 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 117 | 6.2 | 0.068 |
| 10-20 | 102 | 14.6 | 0.186 |
| 20-30 | 49 | 23.8 | 0.265 |
| 30-40 | 12 | 33.3 | 0.167 |
| 40-50 | 2 | 42.6 | 0.5 |
| 50-60 | 10 | 55.3 | 0.9 |
| 60-70 | 12 | 64.0 | 1 |
| 70-80 | 19 | 72.0 | 1 |
| 80-90 | 31 | 80.0 | 1 |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 52.7 | 63.8 | 70 |
| typosquat | 2 | 26.2 | 26.2 | 1 |
| worm | 2 | 21.2 | 21.2 | 0 |

## Takeover slice

Pre-incident replay for 9 historical incidents (event-stream, ua-parser-js, colors, node-ipc, eslint-scope, eslint-config-eslint, coa, rc and xz) is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
