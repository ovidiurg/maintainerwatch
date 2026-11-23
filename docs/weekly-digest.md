# Weekly diff / digest

Compare two compact indexes without a full local database:

```bash
mw diff-index \
  --old maintainerwatch-index-2026-11-16.json \
  --new maintainerwatch-index-2026-11-23.json \
  --format markdown
```

The command reports:

- new high/medium packages;
- resolved high/medium packages;
- changed packages where the band is high/medium or the score moved by at
  least 5 points.

Use `--format json` for a webhook or a custom integration. Versioned index
assets are published in GitHub Releases, so a scheduled job can download two
dated assets and post the Markdown output to an issue or chat channel.

Keep the digest focused on changes. Do not send the full 18k-package dataset
every week.

## Suggested cadence

Run after the public index refresh. Start with a manual digest, then add a
weekly workflow only after the team confirms the signal is useful.
