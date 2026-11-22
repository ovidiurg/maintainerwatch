# Dataset releases

JSON dataset artifacts are published as GitHub Release assets, not committed to
git:

- `dataset-20261122`: 16,526 scored packages, model `0.5.3`, with normalized
  `provider_context` (OSV, deps.dev, Scorecard and consensus);
- checksum: `maintainerwatch-20261122.json.sha256`.

Generate and publish a later snapshot with:

```bash
.venv/bin/mw export --format json
STAMP=20261122 bash scripts/publish_dataset.sh
```

The JSON is large and may contain public maintainer/package metadata; keep raw
exports out of git and review the dual-use/privacy guidance before publishing.
