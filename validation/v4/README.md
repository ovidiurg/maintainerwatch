# Validation v4 — mature fresh-OSV replay holdout

This cohort applies the A2 maturity gate to fresh OSV `MAL-*` advisories:

- published from 2026-01-01 onward;
- package names absent from v1/v2 labels, v1 controls and historical labels;
- **at least 3 versions published before the advisory cutoff**;
- 125 npm positives and the matched v1 controls (998 replayable).

It is a **pre-incident replay holdout**, not a current-state score holdout.
Commit history was not fetched for this sample, so `commit_anomaly` is not
available; the result reflects release metadata only. See
`docs/validation/evaluation-v4.md`.

The cohort is metadata only. Malicious samples are not downloaded or
redistributed.
