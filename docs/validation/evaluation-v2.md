# Validation v2 — expanded sample

Generated from `config/validation-v2.yaml` with the non-OSV positive sample.

## Coverage

- Positives: **489**
- Controls: **1008**
- Positive sources: Datadog 463, tstromberg 65, DependencyWatch 53, OSV 4.
- Cutoff years: 2026 468, 2025 110, 2024 7.

## Full sample

| Positives / controls | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|
| 489 / 1008 | 0.879 | 0.863 | 0.973 / 0.671 / 0.009 |

## Temporal holdout

Positives are split by incident cutoff; controls use their `split` field. The split is diagnostic: the control sample is not a fully historical population.

| Split | Positives / controls | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---|---|---|---|
| train (< 2026) | 120 / 810 | 0.665 | 0.307 | 0.636 / 0.117 / 0.01 |
| test (>= 2026) | 369 / 198 | 0.947 | 0.975 | 0.997 / 0.851 / 0.005 |

## Caveats

- The test slice is recent and larger; train has only 120 positives and 810 controls.
- The sample is still Datadog-heavy; OSV-sourced positives are excluded from headline selection.
- Current-state features can use post-incident information; this is calibration, not proof of predictive performance.
- Temporal groups are small and should not be read as stable population estimates.
