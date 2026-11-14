# Validation evaluation

Generated: 2026-11-14T16:55:10.280770+00:00 · model 0.4.8

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
| Precision@100 | 0.73 |
| AUC | 0.778 |
| PR-AUC / average precision | 0.785 |
| Brier score | 0.1374 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 78 | 89 | 36 | 151 | 0.467 | 0.684 | 0.371 |
| 40.0 | 72 | 6 | 42 | 234 | 0.923 | 0.632 | 0.025 |
| 50.0 | 69 | 0 | 45 | 240 | 1.0 | 0.605 | 0.0 |
| 60.0 | 62 | 0 | 52 | 240 | 1.0 | 0.544 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 1 | 1.0 | 1.0 | 0.143 / 1.0 / 0.025 |
| 2025 | 2 | 0.67 | 0.173 | 0.143 / 0.5 / 0.025 |
| 2026 | 111 | 0.778 | 0.783 | 0.921 / 0.631 / 0.025 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 28 | 7.5 | 0.143 |
| 10-20 | 105 | 14.9 | 0.181 |
| 20-30 | 99 | 24.8 | 0.172 |
| 30-40 | 44 | 33.3 | 0.045 |
| 40-50 | 9 | 43.5 | 0.333 |
| 50-60 | 7 | 52.2 | 1 |
| 60-70 | 12 | 62.7 | 1 |
| 70-80 | 50 | 75.3 | 1 |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 51.6 | 62.9 | 69 |
| typosquat | 2 | 24.6 | 24.6 | 0 |
| worm | 2 | 29.4 | 29.4 | 0 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
