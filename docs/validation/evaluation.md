# Validation evaluation

Generated: 2026-11-13T15:29:22.051803+00:00 · model 0.4.1

> Baseline: current-state scores from the validation ingest, not a pre-incident replay. Use it to compare model versions on the same sample.

## Coverage

- Positives in dataset: 29166
- Positives in validation DB: 114
- Controls in dataset: 1148
- Controls in validation DB: 240

## Ranking metrics

| Metric | Value |
|---|---|
| Precision@10 | 0.9 |
| Precision@25 | 0.96 |
| Precision@50 | 0.98 |
| Precision@100 | 0.76 |
| AUC | 0.819 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 95 | 108 | 19 | 132 | 0.468 | 0.833 | 0.45 |
| 40.0 | 74 | 16 | 40 | 224 | 0.822 | 0.649 | 0.067 |
| 50.0 | 68 | 3 | 46 | 237 | 0.958 | 0.596 | 0.013 |
| 60.0 | 68 | 1 | 46 | 239 | 0.986 | 0.596 | 0.004 |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 47.0 | 60.0 | 67 |
| typosquat | 2 | 21.1 | 21.1 | 0 |
| worm | 2 | 30.6 | 30.6 | 1 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
