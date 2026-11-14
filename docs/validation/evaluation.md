# Validation evaluation

Generated: 2026-11-14T16:37:44.057456+00:00 · model 0.4.8

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

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 76 | 25 | 38 | 215 | 0.752 | 0.667 | 0.104 |
| 40.0 | 72 | 5 | 42 | 235 | 0.935 | 0.632 | 0.021 |
| 50.0 | 69 | 1 | 45 | 239 | 0.986 | 0.605 | 0.004 |
| 60.0 | 62 | 0 | 52 | 240 | 1.0 | 0.544 | 0.0 |

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
