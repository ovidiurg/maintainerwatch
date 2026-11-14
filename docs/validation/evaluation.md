# Validation evaluation

Generated: 2026-11-14T08:29:16.318071+00:00 · model 0.4.6

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
| Precision@100 | 0.75 |
| AUC | 0.849 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 76 | 26 | 38 | 214 | 0.745 | 0.667 | 0.108 |
| 40.0 | 69 | 5 | 45 | 235 | 0.932 | 0.605 | 0.021 |
| 50.0 | 44 | 0 | 70 | 240 | 1.0 | 0.386 | 0.0 |
| 60.0 | 43 | 0 | 71 | 240 | 1.0 | 0.377 | 0.0 |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 40.8 | 48.0 | 44 |
| typosquat | 2 | 13.7 | 13.7 | 0 |
| worm | 2 | 25.1 | 25.1 | 0 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
