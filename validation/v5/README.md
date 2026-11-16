# Validation v5 — fresh current-state cohort

This is a current-state diagnostic cohort selected from the fresh OSV MAL intake:

- advisory published from 2026-01-01 onward;
- package absent from v1/v2 positives, v1 controls and historical labels;
- package still present in the expanded local registry DB;
- the package's **latest version is explicitly listed in the OSV
  `affected_versions` set**.

It contains **108 npm positives** and the matched v1 controls. The label means
the current latest version is affected by a fresh OSV MAL advisory, not that the
package was necessarily malicious at an earlier cutoff.

This is a current-state diagnostic cohort, not a historical/replay cohort. It is
not yet wired into `mw calibrate`; the OSV signal ablation is reported alongside
the metrics so the label-source overlap is visible. See
`docs/validation/evaluation-v5.md`.

The cohort is metadata only. Malicious samples are not downloaded or
redistributed.
