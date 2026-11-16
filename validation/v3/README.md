# Validation v3 — fresh OSV MAL cohort

This is a **fresh-label diagnostic cohort**, not a cleared model holdout.

- Labels: OSV `MAL-*` advisories published from 2026-01-01 onward.
- Selection: advisory IDs absent from the local OSV table; package names absent
  from v1/v2 positives, v1 controls and the historical cohort.
- Sampling: 600 npm + 15 PyPI unique packages; 381 npm packages survived
  registry ingestion. PyPI packages were already removed.
- Controls: the matched v1 control set (`controls.jsonl`); 998 are replayable in
  the v3 database.
- Cutoff: OSV publication time minus one day.
- Review: `approved_osv_mal` after an automated source/scope check. This is not
  a claim that every advisory has manually reconstructed compromise timing.

The cohort is dominated by new/spam packages. In pre-incident replay, **326 of
381** positives have no applicable pre-cutoff signal, and the resulting AUC is
**0.209**. It must not be used for model tuning or as evidence of model quality.
See `docs/validation/evaluation-v3.md`.

The dataset is metadata only. Malicious samples are not downloaded or
redistributed.
