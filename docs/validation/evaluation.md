# Validation evaluation

Generated: 2026-11-14T16:47:56.290712+00:00 · model 0.4.8

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
| AUC | 0.864 |
| PR-AUC / average precision | 0.839 |
| Brier score | 0.1227 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 76 | 25 | 38 | 215 | 0.752 | 0.667 | 0.104 |
| 40.0 | 72 | 5 | 42 | 235 | 0.935 | 0.632 | 0.021 |
| 50.0 | 69 | 1 | 45 | 239 | 0.986 | 0.605 | 0.004 |
| 60.0 | 62 | 0 | 52 | 240 | 1.0 | 0.544 | 0.0 |

## Temporal slices

| Cutoff year | Positives | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| 2024 | 1 | 1.0 | 1.0 | 0.167 / 1.0 / 0.021 |
| 2025 | 2 | 0.507 | 0.254 | 0.167 / 0.5 / 0.021 |
| 2026 | 111 | 0.869 | 0.839 | 0.933 / 0.631 / 0.021 |

## Calibration

| Score bin | Count | Mean score | Positive rate |
|---|---|---|---|
| 0-10 | 124 | 5.7 | 0.056 |
| 10-20 | 88 | 14.7 | 0.227 |
| 20-30 | 51 | 23.5 | 0.255 |
| 30-40 | 14 | 34.2 | 0.143 |
| 40-50 | 7 | 42.5 | 0.429 |
| 50-60 | 8 | 52.1 | 0.875 |
| 60-70 | 12 | 62.7 | 1 |
| 70-80 | 50 | 75.3 | 1 |
| 80-90 | 0 | None | None |
| 90-100 | 0 | None | None |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 51.0 | 62.9 | 69 |
| typosquat | 2 | 24.6 | 24.6 | 0 |
| worm | 2 | 21.2 | 21.2 | 0 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
