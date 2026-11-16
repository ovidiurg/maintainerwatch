# Fresh current-state cohort (v5)

Generated 2026-11-16 from fresh OSV `MAL-*` advisories where the current latest
package version is explicitly listed as affected.

## Cohort

| Item | Value |
|---|---:|
| Incidents / packages | 108 / 108 |
| Ecosystem | npm |
| Latest versions confirmed affected | 108 / 108 |
| Controls in dataset | 1,148 |
| Scored controls | 1,008 |

The cohort is selected from packages that survived registry ingestion and are
absent from v1/v2 labels. It is a **current-state** cohort: the label is based
on the latest version, not a reconstructed pre-incident cutoff.

## Current model (0.5.3)

| Metric | Value |
|---|---:|
| AUC | 0.931 |
| PR-AUC / average precision | 0.629 |
| Brier score | 0.0625 |
| Precision@10 / @25 / @50 / @100 | 1.000 / 0.960 / 0.800 / 0.530 |
| Threshold 25: precision / recall / FPR | 0.419 / 0.620 / 0.092 |
| Threshold 40: precision / recall / FPR | 0.744 / 0.269 / 0.010 |
| Threshold 50: precision / recall / FPR | 0.963 / 0.241 / 0.001 |
| Threshold 60: precision / recall / FPR | 1.000 / 0.204 / 0.000 |

## Signal ablations

The baseline is AUC 0.931 / AP 0.629. Notable leave-one-out deltas:

| Removed signal | Delta AUC | Delta AP |
|---|---:|---:|
| `publisher_change` | **+0.043** | **+0.152** |
| `release_anomaly` | **+0.035** | **+0.113** |
| `dependency_risk` | +0.017 | +0.060 |
| `signing_gap` | **-0.490** | **-0.488** |
| `typosquat` | -0.012 | -0.033 |
| `license_inconsistency` | -0.007 | -0.014 |
| `osv_risk` | 0.000 | 0.000 |

The negative `signing_gap` ablation is a warning about the label/source mix:
the current cohort contains many unsigned or provenance-missing packages, so
the signal is not behaving as an independent discriminator here. Do not tune
on v5; use it as a current-state diagnostic and a candidate for a future
properly frozen calibration cohort.
