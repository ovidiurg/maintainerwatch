# Validation evaluation

Generated: 2026-11-13T15:59:33.702232+00:00 · model 0.4.3

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
| Precision@100 | 0.73 |
| AUC | 0.85 |

## Threshold metrics

| Threshold | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---|---|---|---|---|---|---|
| 25.0 | 82 | 36 | 32 | 204 | 0.695 | 0.719 | 0.15 |
| 40.0 | 68 | 6 | 46 | 234 | 0.919 | 0.596 | 0.025 |
| 50.0 | 46 | 1 | 68 | 239 | 0.979 | 0.404 | 0.004 |
| 60.0 | 45 | 1 | 69 | 239 | 0.978 | 0.395 | 0.004 |

## Positives by attack type

| Type | Count | Mean | Median | High |
|---|---|---|---|---|
| malicious_package | 110 | 42.3 | 48.0 | 45 |
| typosquat | 2 | 21.1 | 21.1 | 0 |
| worm | 2 | 27.6 | 27.6 | 1 |

## Takeover slice

Pre-incident replay for event-stream, ua-parser-js, colors, node-ipc and xz is in [incident-validation.md](../incident-validation.md).

## Caveats

- Current-state scores, not time-aware replay; historical features may leak.
- The validation DB only contains packages that were still ingestible.
- Controls are matched negatives, not guaranteed benign.
- Metrics are case-control, not population estimates.
