# Dataset releases

Dataset artifacts are published as GitHub Release assets, not committed to git.

Current snapshot:

- `snapshot-20261123`
- 18,665 scored packages
- model `0.5.3`
- JSON with normalized `provider_context`
- Parquet, CSV, SPDX, CycloneDX, OSV, HTML report
- compact CI index and checksums

Generate a later snapshot with:

```bash
.venv/bin/mw export --format json
.venv/bin/mw export --format parquet
.venv/bin/mw report --out data/report.html
make ci-index
```

Then publish the snapshot assets manually or adapt `scripts/publish_dataset.sh`.
Raw exports and databases stay out of git; review the dual-use/privacy guidance
before publishing.
