# Validation evaluation

Generated: 2026-11-14T14:15:43.990045+00:00 · model 0.4.7

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
| AUC | 0.857 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 76 | 26 | 38 | 214 | 0.745 | 0.667 | 0.108 |
| 40.0 | 70 | 5 | 44 | 235 | 0.933 | 0.614 | 0.021 |
| 50.0 | 63 | 1 | 51 | 239 | 0.984 | 0.553 | 0.004 |
| 60.0 | 63 | 0 | 51 | 240 | 1.0 | 0.553 | 0.0 |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 47.3 | 60.0 | 63 |
| typosquat | 2 | 19.2 | 19.2 | 0 |
| worm | 2 | 22.5 | 22.5 | 0 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
