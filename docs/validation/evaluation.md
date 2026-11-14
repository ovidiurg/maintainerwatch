# Validation evaluation

Generated: 2026-11-13T17:40:53.002114+00:00 · model 0.4.5

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
| Precision@50 | 0.98 |
| Precision@100 | 0.75 |
| AUC | 0.846 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 75 | 26 | 39 | 214 | 0.743 | 0.658 | 0.108 |
| 40.0 | 68 | 5 | 46 | 235 | 0.932 | 0.596 | 0.021 |
| 50.0 | 43 | 1 | 71 | 239 | 0.977 | 0.377 | 0.004 |
| 60.0 | 43 | 0 | 71 | 240 | 1.0 | 0.377 | 0.0 |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 40.5 | 48.0 | 43 |
| typosquat | 2 | 13.7 | 13.7 | 0 |
| worm | 2 | 22.5 | 22.5 | 0 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
