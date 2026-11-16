# Validation v4 — mature fresh-OSV replay holdout

This cohort applies the A2 maturity gate to fresh OSV `MAL-*` advisories:

- published from 2026-01-01 onward;
- package names absent from v1/v2 labels, v1 controls and historical labels;
- **at least 3 versions published before the advisory cutoff**;
- 125 npm positives and the matched v1 controls (998 replayable).

It is a **pre-incident replay holdout**, not a current-state score holdout.
Commit history was backfilled for **60 / 125** packages (9,742 commits) using
`python scripts/backfill_validation_commits.py --dataset validation/v4 \
--config config/validation-v4.yaml --positives-only`. The remaining 65 split
between 43 packages with no repository URL and 22 with a repository but no
pre-cutoff commits (including deleted/private/fake repos). See
`docs/validation/evaluation-v4.md`.

The cohort is metadata only. Malicious samples are not downloaded or
redistributed.
