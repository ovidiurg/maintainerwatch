# Validation dataset (v1)

Hybrid metadata dataset for calibrating MaintainerWatch: malicious-package
incidents, historical incident context and matched benign controls. **Only
metadata is stored here.** Malicious samples are not downloaded, included or
redistributed.

## Files

| File | Contents |
|---|---|
| `incidents.jsonl` | One row per incident/campaign (620 rows). |
| `incident_packages.jsonl` | One row per affected package/incident (31,485 rows). |
| `controls.jsonl` | Matched benign controls (1,148 rows). |
| `sources.yaml` | Source registry with licences and attribution. |
| `manifest.json` | Counts, hashes, source list, generation time. |

Current counts (2026-11-13): **620 incidents**, **31,485 incident packages**,
**1,148 controls**. Recent incidents (2024+) are prioritised: 529 of 620
incidents are high priority.

## Preliminary evaluation (2026-11-13)

A case-control sample was ingested into `data/validation` (120 positives plus
120 matched controls per npm/PyPI seed list). 354 packages were scored; the
database retained **114 positives** and **240 controls** (most PyPI malicious
packages had already been removed).

| Metric | Value |
|---|---|
| AUC | 0.875 |
| PR-AUC / average precision | 0.855 |
| Brier score | 0.1164 |
| Precision@10 / @25 / @50 / @100 | 1.0 / 1.0 / 1.0 / 0.80 |
| Threshold 40: precision / recall / FPR | 0.973 / 0.632 / 0.008 |
| Threshold 50: precision / recall / FPR | 0.986 / 0.623 / 0.004 |

The sample is npm-heavy and dominated by `malicious_package`; the takeover
slice is reported separately in `docs/incident-validation.md`. The generated
report also includes temporal slices by cutoff year (`mw evaluate-validation
--since ... --until ...`) and calibration bins. Temporal groups are very small,
so treat them as diagnostics, not stable estimates. OSV and deps.dev
findings are known-advisory signals, so current-state metrics can overlap with
the label sources; treat them as triage evidence, not independent predictive
proof. See
`docs/validation/evaluation.md` for the generated report and caveats.


## Historical-only cohort

`validation/historical/` contains 30 manually reviewed OSV `MAL-*` labels whose
malicious versions have been removed from the registry. They are kept for
historical/version-aware work and are **not** part of the v1 current-state
metrics. Promoting historical labels directly into v1 makes current-state
metrics artificially pessimistic.

## Validation v2 — expanded sample

`config/validation-v2.yaml` and `scripts/prepare_validation_v2_sample.py` define
a larger, year-stratified, non-OSV positive sample. The local DB currently has
**489 positives** and **1,008 controls**.

| Sample | AUC | PR-AUC | Threshold-40 precision / recall / FPR |
|---|---:|---:|---|
| Full | 0.891 | 0.878 | 0.970 / 0.671 / 0.010 |
| Train (<2026) | 0.705 | 0.269 | 0.474 / 0.082 / 0.010 |
| Test (>=2026) | 0.953 | 0.940 | 0.969 / 0.851 / 0.010 |

The full-sample Brier score is **0.1332**. The positive mix is Datadog 463, tstromberg 65, DependencyWatch 53, OSV 4;
cutoffs are 2026: 468, 2025: 110, 2024: 7. The temporal split is diagnostic,
not a fully historical control population. Running
`mw evaluate-validation --config config/validation-v2.yaml` writes
`validation/v2/evaluation.json` and `docs/validation/evaluation-v2.md` without
overwriting the v1 report. See `docs/validation/evaluation-v2.md`.

## Pre-incident replay

`python scripts/validation_replay.py` rebuilds each package using only versions
and commits before its incident cutoff. Historical commits are backfilled with
`scripts/backfill_validation_commits.py`.

| Replay metric | Value |
|---|---|
| Positives / controls replayable | 114 / 240 |
| Positives with any applicable signal | 63 |
| Positives with no pre-cutoff history | 51 |
| AUC | 0.485 |
| Threshold 40: precision / recall / FPR | 0.596 / 0.272 / 0.087 |
| Threshold 50: precision / recall / FPR | 0.660 / 0.272 / 0.067 |

This is much lower than the current-state evaluation because many malicious
packages are new at the incident cutoff and have no usable release/commit
history. The current-state numbers must not be read as predictive performance.
Replay output is written to `data/validation/replay.json` (git-ignored).

## Schema (summary)

### `incidents.jsonl`
`incident_id`, `title`, `ecosystem`, `systems`, `attack_type`, `summary`,
`first_compromise_date`, `disclosure_date`, `removal_date`,
`observation_cutoff`, `cutoff_basis`, `severity`, `source_urls`,
`source_types`, `source_licenses`, `confidence`, `sample_available`,
`priority`, `notes`, `schema_version`, `dataset_version`.

`attack_type` is one of: `account_takeover`, `maintainer_sabotage`,
`typosquat`, `dependency_confusion`, `malicious_package`, `worm`,
`protestware`, `unknown`.

`observation_cutoff` is the last timestamp from which features may be
computed. It must be **before** the malicious release or disclosure.

### `incident_packages.jsonl`
`incident_id`, `system`, `package`, `affected_versions`, `label`,
`label_confidence`, `source`, `source_urls`, `sample_available`, `notes`,
`schema_version`, `dataset_version`.

### `controls.jsonl`
`control_id`, `system`, `package`, `as_of`, `label` (`benign`),
`matched_incident_id`, `match_features`, `source`, `exclusion_checks`, `split`,
`schema_version`, `dataset_version`.

Controls are sampled from the local MaintainerWatch database and are **not
guaranteed benign**; they are matched negative examples, not ground truth.

## Sources and licences

| Source | Licence / access | Role |
|---|---|---|
| OpenSSF Malicious Packages / OSV `MAL-*` | Apache-2.0, public | Primary positives; recent records prioritised. |
| DependencyWatch.io | Free reuse with attribution | Recent incident/package metadata. |
| Datadog malicious packages dataset | Apache-2.0 metadata; encrypted samples | Snapshot positives (no per-package discovery date). |
| tstromberg/upstream-supplychain-attacks | Apache-2.0 | Incident context and historical packages. |
| MalOSS | MIT lists; samples restricted | Historical positive lists. |
| ML/industry reports | Public reports | Curated takeover/sabotage dossiers (`manual`). |

Full attribution and per-source notes are in `sources.yaml`.

## Rebuild and validate

```bash
python scripts/build_validation_dataset.py
python scripts/check_validation_dataset.py
```

The builder fetches source metadata, normalises it, deduplicates and writes the
JSONL files. It does not fetch samples. The check script verifies required
fields, incident references, cutoff ordering, control overlap and manifest
counts.

## Known limitations

- Some OSV incidents are **synthetic groupings** by month, ecosystem and attack
  type; they preserve package metadata but not a single campaign identity.
- Snapshot sources (DataDog, MalOSS) lack per-package discovery dates; their
  cutoffs are conservative but not incident-specific.
- Historical repository/scorecard/dependency features are current-state and
  must not be used for time-aware replay unless historical snapshots exist.
- The positive class is dominated by npm and PyPI; report metrics per ecosystem.
- Malicious packages are often removed; `sample_available` records whether code
  is known to exist, not whether it is still downloadable.
- Sources can contain false positives or researcher probes; label confidence is
  recorded and should be reported separately.
- `manifest.json` contains SHA-256 file digests; these are high-entropy by
  design and are not secrets. The JSONL metadata is public package/incident
  data and is scanned separately for token patterns.

## Ethics

The dataset contains public metadata about malicious packages and public
maintainer identities. Do not use it for doxxing, harassment or automated
accusations. Verify findings before contacting maintainers or publishing. Follow
the licence and attribution requirements of each source.
