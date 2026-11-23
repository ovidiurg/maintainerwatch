# Changelog

Public data/model/index changes for MaintainerWatch. The dataset is a research
preview, not a live malware verdict feed.

## 2026-11-23

### Dataset and model

- Published `snapshot-20261123`: **18,665 scored packages**
  - 8,660 npm, 7,050 PyPI, 2,350 crates, 501 Maven, 104 GitHub
- Model **0.5.3**; app **0.4.23**
- 2,193,716 versions, 317,955 commits, 36,868 maintainers, 10,967 OSV records,
  65,741 dependency edges
- Risk bands: **15 high, 3,901 medium, 14,749 low**
- 11 high-band packages are advisory/behaviour-confirmed; four remain review
  cases
- deps.dev impact rows: 16,728; deps.dev findings: 18,533; Scorecard scores:
  2,621

### Index and CI

- Compact index updated with the top three signals per package.
- Public index: `maintainerwatch-index.json` (4.7 MB, 18,665 records).
- Current index checksum:
  `facc736898bd8f790d7b56bba2808b9519d90a00e0086f1cf2ceb6da1c442258`.
- Added the public package lookup and first-10-minutes page on Pages.
- Added `mw lookup PACKAGE --system SYSTEM` for the public index without ingest.
- Added expiring waivers for `scan-diff` and the GitHub Action.
- Added `mw diff-index` for weekly high/medium changes.
- Added opt-in feedback intake through the issue form.

### Database and operations

- `scorecard_history` seeded with 2,621 baseline observations from current
  Scorecard scores.
- Added score band/system indexes and removed unused/redundant indexes.
- Version reads now use `idx_versions_pkg` ordering.
- Local DB reduced to ~1.2 GB after cleanup and `VACUUM`.
- Tests: **212 passed**, coverage **77.37%**.

## 2026-11-22

- Published `snapshot-20261122`: **18,652 scored packages**, model `0.5.3`.
- Included JSON, Parquet, CSV, SPDX, CycloneDX, OSV, HTML report and compact
  index assets.

## Verification

```bash
mw lookup lodash --system npm
curl -fsSL https://github.com/ovidiurg/maintainerwatch/releases/latest/download/maintainerwatch-index.json -o index.json
sha256sum index.json
```

Public assets:

- <https://github.com/ovidiurg/maintainerwatch/releases>
- <https://ovidiurg.github.io/maintainerwatch/>

## Known limitations

- The sample is not the full npm/PyPI/crates/Maven/GitHub universe.
- Four high-band packages are review cases, not malware labels; see
  [high-band review](validation/high-band-review.md).
- v6 is a frozen current-state holdout with no unseen labels yet. Do not compute
  v6 metrics until labels exist.
- v3/v4/v5 are diagnostics, not production tuning sets.
- OSV affected ranges are incomplete for some records; coverage is reported
  rather than guessed.
- The public index is a static snapshot, not real-time telemetry.
