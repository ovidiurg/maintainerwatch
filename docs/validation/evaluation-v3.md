# Fresh OSV MAL replay cohort (v3)

Generated 2026-11-16 from fresh OSV `MAL-*` advisories. This report is a
data-selection diagnostic, **not** a model-quality result.

## Cohort

| Item | Value |
|---|---:|
| Incidents / packages | 381 / 381 |
| Ecosystem | npm |
| Advisories published | 2026-01-01 onward |
| Controls in dataset | 1,148 |
| Replayable controls | 998 |
| Replayable positives | 381 |
| Positives with applicable pre-cutoff signals | 55 |
| Positives with no pre-cutoff history | 326 |

The sample was selected from fresh advisories absent from the v1/v2 labels and
the local OSV table. Only 381 of 615 sampled packages survived registry
ingestion; PyPI yielded none.

## Replay result

| Metric | Value |
|---|---:|
| AUC | 0.209 |
| Precision@10 | 0.900 |
| Precision@25 | 0.800 |
| Precision@50 | 0.400 |
| Threshold 40: precision / recall / FPR | 0.222 / 0.084 / 0.112 |
| Threshold 50: precision / recall / FPR | 0.177 / 0.058 / 0.102 |
| Threshold 60: precision / recall / FPR | 0.185 / 0.058 / 0.097 |

## Verdict

**Rejected as a model holdout.** The cohort is dominated by new packages and
spam-like publications; 326 of 381 positives have no usable pre-cutoff release
history. The lower-than-random AUC reflects this selection bias and the fact
that controls are older packages with different baseline signals. It is useful
as a data-quality and selection-bias diagnostic, not as calibration evidence.

Do not tune weights on v3. No model change was made.

## Next step

A2: expand the mature-package universe before selecting another independent
cohort. Prefer candidates that have at least three pre-cutoff versions and,
where available, pre-cutoff commits. Report coverage before metrics.
