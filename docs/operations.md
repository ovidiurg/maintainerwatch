# Operations

MaintainerWatch is a batch pipeline plus a read-only API. A typical deployment
runs ingestion and maintenance on a schedule, records maintainer snapshots
daily, and serves the resulting SQLite database through `mw serve`.

## Daily pipeline

```bash
# 1. Refresh registry metadata (adjust --top to your budget).
mw ingest --system npm --top 500
mw ingest --system pypi --top 500
mw ingest --system crates --top 100
mw ingest --system maven --top 50
mw ingest --system github --top 1
mw enrich-impact --limit 500
mw enrich-findings --limit 500
mw enrich-scorecard --limit 500
mw scan-content --limit 50
# mw scan-guarddog --limit 20  # requires guarddog
# mw scan-dynamic --limit 20   # requires dynamic.worker_url + worker/
mw backfill-osv --limit 500 --malicious-only

# 2. Rebuild derived data, record snapshots, rescore, export.
mw maintain

# 3. Weekly validation (precision/recall and known misses).
python scripts/incident_check.py
```

`mw maintain` runs `backfill-deps`, `backfill-licenses`, `backfill-commits`,
`resolve`, `record_current_snapshots`, `score-all`, every export format and the
HTML report. Use `--no-with-commits` to skip commit refreshes, `--limit N` for
a small run, or `--no-export` to skip files.

`mw snapshot` records only the current maintainer snapshots; run it daily even
when ingestion is less frequent, so PyPI `publisher_change` has history.

## Cron

```cron
# Nightly ingest and maintenance, weekly validation.
0 2 * * * cd /opt/maintainerwatch && . .venv/bin/activate && mw ingest --system npm --top 500 >> logs/ingest.log 2>&1
30 2 * * * cd /opt/maintainerwatch && . .venv/bin/activate && mw ingest --system pypi --top 500 >> logs/ingest.log 2>&1
0 3 * * * cd /opt/maintainerwatch && . .venv/bin/activate && mw maintain >> logs/maintain.log 2>&1
0 4 * * 0 cd /opt/maintainerwatch && . .venv/bin/activate && python scripts/incident_check.py >> logs/validation.log 2>&1
```

Create `logs/` first. Keep `GITHUB_TOKEN`, `GITLAB_TOKEN` and
`MAINTAINERWATCH_API_KEY` in the service environment, not in the crontab.

## systemd timer

`/etc/systemd/system/maintainerwatch.service`:

```ini
[Unit]
Description=MaintainerWatch maintenance
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/maintainerwatch
Environment=GITHUB_TOKEN=...
ExecStart=/opt/maintainerwatch/.venv/bin/mw maintain
```

`/etc/systemd/system/maintainerwatch.timer`:

```ini
[Unit]
Description=Run MaintainerWatch nightly

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with `systemctl enable --now maintainerwatch.timer`.

## Docker

```bash
# Build and serve with a bind-mounted data directory.
docker compose up -d --build
curl http://127.0.0.1:8000/health

# Run a one-off job in the same image.
docker compose run --rm api mw ingest --system npm --top 100
docker compose run --rm api mw maintain

# Generate the static report into the mounted data directory.
docker compose run --rm api mw report --out /app/data/report.html
ls -lh data/report.html

# Serve it locally if you do not want to open file:// directly.
python3 -m http.server 8080 --directory data
# http://127.0.0.1:8080/report.html
```

`docker-compose.yml` runs the container as the host UID/GID and mounts
`./data`; make sure that directory is writable. The API serves JSON only; the
HTML report is a static file generated into `/app/data/report.html`. `mw
maintain` writes `data/report.html` in the same volume. For a read-only API deployment,
the container only needs read access to the SQLite file and its `-wal`/`-shm`
companions.

## Calibration loop

Run the baseline calibration and drift report weekly, without retuning weights:

```cron
0 5 * * 1 cd /opt/maintainerwatch && . .venv/bin/activate && make calibration-loop >> logs/calibration.log 2>&1
```

`make calibration-loop` writes `validation/calibration/history.jsonl` and
`docs/validation/calibration-drift.md`. If the local v4 validation database is
present, it also writes `validation/calibration/replay-history.jsonl` and
`docs/validation/replay-drift.md`. It intentionally does **not** run
`mw calibrate --search`; repeated search against the same v2 test slice would
overfit the holdout. Use search only with a new/rolling holdout.

Run the v4 replay checkpoint directly with:

```bash
make replay-v4
```

## Database performance

The schema is indexed for the read paths used by the API, report and scoring,
including:
`packages(system, downloads_weekly)`, `scores(model_version, score)`,
`signals(model_version, system, name)`, `osv(vuln_id)`, and expression indexes
for the case-insensitive dependency, maintainer and publisher lookups. Existing
databases get the indexes on the next `mw init`/`mw ingest`/`mw serve` call;
no manual migration is required.

Connections use WAL, `synchronous=NORMAL`, a 32 MB page cache and a 5 s busy
timeout. Ingestion defers commits while it processes a package batch, so large
seed runs do not pay one fsync per package. The dependency refresh uses the
lower-name indexes instead of correlated full scans.

For a large one-off rebuild after deleting/importing many packages, run:

```bash
sqlite3 data/maintainerwatch.sqlite "PRAGMA optimize;"
sqlite3 data/maintainerwatch.sqlite "VACUUM;"
```

`VACUUM` needs free disk space roughly equal to the database size and should
run while the API is stopped. Do not run it from cron on every ingest.

## OSV archive backfill

If a local npm/PyPI OSV archive is available, fill stored advisory affected
ranges without thousands of per-advisory API calls:

```bash
.venv/bin/python scripts/backfill_osv_archive.py \
  --npm-zip /path/npm-all.zip --pypi-zip /path/pypi-all.zip
```

Then rerun `mw score-all` so `osv_risk` sees the new ranges.

## GitLab forge backfill

GitLab repository support uses the GitLab API, which rate-limits unauthenticated
requests. Set `GITLAB_TOKEN` and run:

```bash
python scripts/backfill_gitlab.py --commits
```

The script only selects `gitlab.com` URLs; self-hosted GitLab URLs need a
separate API host and are not covered by the public API path.

## DB performance notes

The database uses WAL, a 32 MB page cache, a busy timeout and expression
indexes for case-insensitive dependency/maintainer lookups. Scorecard
observations are stored in `scorecard_history` with a package index so trends
do not require a table scan.

The JSON export builds provider context in bulk (`providers.bulk_context`)
instead of re-querying OSV/deps.dev/Scorecard once per package. Maintainer
exposure queries start from `maintainers` so `idx_maintainers_identity_lower`
is used. Typosquat matching uses bounded Damerau-Levenshtein with a cap of 2;
profiling 200 packages dropped scoring time from ~9.2s to ~1.0s. Keep long
operations in local batch scripts; the HTTP API stays read-only and uses
single-package queries.

## Dataset release

Publish the JSON dataset as a GitHub Release asset:

```bash
.venv/bin/mw export --format json
STAMP=20261122 bash scripts/publish_dataset.sh
```

See `docs/dataset-releases.md`. Do not commit the raw JSON or database.

## Provider cohort backfill

Backfill deps.dev findings/impact for the current high and medium cohorts:

```bash
.venv/bin/python scripts/backfill_provider_cohorts.py --limit 1000
```

Backfill repository/Scorecard data for those cohorts:

```bash
.venv/bin/python scripts/backfill_provider_cohorts.py --providers github --limit 500
# Tail only (<1,000 downloads/week):
.venv/bin/python scripts/backfill_provider_cohorts.py --providers github --bands low --max-downloads 999 --limit 500
```

Some packages have no supported repository or no provider record; those remain
`unavailable`/`unknown` and should not be treated as clean negatives.

## Provider context audit

Check provider agreement for the current high-band packages:

```bash
.venv/bin/python scripts/provider_context_audit.py
```

It writes `data/validation/provider-context-audit.json` and
`docs/validation/provider-context-audit.md`. It is read-only and does not change
scores.

## Backups

SQLite is a single file plus `-wal`/`-shm` while connections are open. Use the
SQLite backup command for a consistent copy:

```bash
sqlite3 data/maintainerwatch.sqlite ".backup 'backups/maintainerwatch-$(date +%F).sqlite'"
```

Back up `data/` (database, exports, report) and the `logs/` directory.

## Monitoring

- `GET /health` returns the app and model version.
- `GET /systems` shows per-ecosystem package counts.
- `/alert-rules` runs the configured rules without delivering them; use
  `mw alerts --rules` for webhook/email delivery.
- Watch the maintenance log for `backfill` and `resolve` errors; most sources
  are best-effort and report failures per package.

## Security and responsible use

- Treat `data/maintainerwatch.sqlite`, backups and exports as sensitive: they
  contain maintainer identifiers and public email fields. Restrict filesystem
  access and encrypt backups where appropriate.
- The API is read-only but exposes ranked package risk and maintainer evidence.
  Bind it to localhost by default; for a public deployment add
  `MAINTAINERWATCH_API_KEY`, rate limits, a TLS reverse proxy and minimal logs.
- Do not publish raw databases, maintainer dossiers or ranked target lists.
  Publish aggregate findings only, with identities minimised.
- Bulk ingestion should use `--no-github`; bound `mw enrich-github` with
  `--limit` and `--pages` to control GitHub API use.
- Use findings for defence, maintenance and coordinated disclosure, not for
  automated accusations or harassment of maintainers.

For a removal request, use the private channel in [docs/gdpr.md](gdpr.md);
operators can run `mw delete-package --system SYSTEM --name PACKAGE --yes`
(without `--yes` for a dry-run). See the dual-use section in
[README.md](../README.md).

## Retention

- HTTP responses are cached under `data/cache/` with a short TTL; safe to
  delete when the service is stopped.
- Snapshots accumulate; one per package per day is enough. Avoid running
  `mw snapshot` more than a few times a day.
- Exports are overwritten per day (`maintainerwatch-YYYYMMDD.*`).
