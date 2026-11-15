# Historical-only validation cohort

This directory contains 30 manually reviewed OSV `MAL-*` labels that were
promoted through the feedback loop but are not part of the v1 current-state
cohort.

Reason: their affected versions are no longer present in the registry, so a
current-state package score cannot fairly evaluate the historical compromise.
Use these records for historical/version-aware replay work, not for the v1
current-state AUC/PR-AUC metrics.

Files:

- `incidents.jsonl`
- `incident_packages.jsonl`

The source URL for every row is preserved. `cutoff_basis` is
`osv_published_minus_1d`; this is a conservative publication-date cutoff, not a
reconstruction of the exact compromise time.
