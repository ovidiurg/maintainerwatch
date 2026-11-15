# Validation evaluation

Generated: 2026-11-15T22:21:11.688529+00:00 · model 0.5.2

> Baseline: current-state scores from the validation ingest, not a pre-incident replay. Use it to compare model versions on the same sample.

## Coverage

- Positives in dataset: 29196
- Positives in validation DB: 144
- Controls in dataset: 1148
- Controls in validation DB: 240

## Ranking metrics

| Metric | Value |
|---|---|
| Precision@10 | 1.0 |
| Precision@25 | 1.0 |
| Precision@50 | 1.0 |
| Precision@100 | 0.87 |
| AUC | 0.848 |
| PR-AUC / average precision | 0.832 |
| Brier score | 0.1605 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 90 | 20 | 54 | 220 | 0.818 | 0.625 | 0.083 |
| 40.0 | 73 | 1 | 71 | 239 | 0.986 | 0.507 | 0.004 |
| 50.0 | 69 | 0 | 75 | 240 | 1.0 | 0.479 | 0.0 |
| 60.0 | 62 | 0 | 82 | 240 | 1.0 | 0.431 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2023 | 17 | 0.772 | 0.182 | 0.0 / 0.0 / 0.004 |
| 2024 | 1 | 1.0 | 1.0 | 0.5 / 1.0 / 0.004 |
| 2025 | 15 | 0.783 | 0.282 | 0.667 / 0.133 / 0.004 |
| 2026 | 111 | 0.867 | 0.838 | 0.986 / 0.631 / 0.004 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 129 | 6.0 | 0.07 |
| 10-20 | 110 | 14.7 | 0.309 |
| 20-30 | 60 | 24.5 | 0.45 |
| 30-40 | 11 | 33.7 | 0.091 |
| 40-50 | 5 | 46.5 | 0.8 |
| 50-60 | 7 | 52.2 | 1 |
| 60-70 | 12 | 62.7 | 1 |
| 70-80 | 50 | 75.3 | 1 |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 140 | 44.5 | 47.4 | 69 |
| typosquat | 2 | 24.7 | 24.7 | 0 |
| worm | 2 | 21.0 | 21.0 | 0 |

## Takeover slice

Pre-incident replay for 9 historical incidents (event-stream, ua-parser-js, colors, node-ipc, eslint-scope, eslint-config-eslint, coa, rc and xz) is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
