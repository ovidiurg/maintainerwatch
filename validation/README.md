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
| AUC | 0.849 |
| Precision@10 / @25 / @50 / @100 | 1.0 / 1.0 / 1.0 / 0.75 |
| Threshold 40: precision / recall / FPR | 0.932 / 0.605 / 0.021 |
| Threshold 50: precision / recall / FPR | 1.0 / 0.386 / 0.0 |

The sample is npm-heavy and dominated by `malicious_package`; the takeover
slice is reported separately in `docs/incident-validation.md`. See
`docs/validation/evaluation.md` for the generated report and caveats.

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
