# Validation v6 — frozen current-state snapshot

This is the **snapshot half** of a clean current-state holdout. The snapshot is
frozen; labels are pending.

- Snapshot: `data/validation-v6/maintainerwatch.sqlite`
- Source: current main DB at 2026-11-21
- SHA-256: `manifest.json`
- Excluded from labels/controls: v1, v2, v3, v4, v5 and historical cohorts
- Controls: to be sampled from the frozen snapshot, matched by ecosystem and
  download band

No model metrics have been computed on v6. Do not inspect or tune on it until
labels are frozen with `scripts/build_holdout.py`.

## Why labels are pending

A fresh OSV dump on 2026-11-21 produced **zero** new current-state positives
that were absent from the earlier validation sets. Publishing a holdout from
the same labels would not be clean. The next v6 labels must come from a future
OSV/advisory intake, after this snapshot date.

## Weekly intake

Cron runs every Monday at 05:30:

```bash
.venv/bin/python scripts/intake_v6_labels.py >> logs/v6-intake.log 2>&1
```

It downloads the current OSV npm/PyPI archives, filters MAL advisories published
after the frozen snapshot date, keeps only packages whose latest version is
listed as affected, and excludes every package already used in v1–v5 or the
historical cohort. It writes `data/validation-v6/new-osv-labels.jsonl` and does
not compute or inspect model metrics.

Current state: **0 new labels** as of 2026-11-21; the holdout remains
`awaiting_labels`.

## Build command

```bash
python scripts/build_holdout.py \
  --snapshot-db data/validation-v6/maintainerwatch.sqlite \
  --labels data/validation-v6/new-osv-labels.jsonl
```

The builder refuses fewer than 50 positives and writes a frozen protocol with
the snapshot hash.
