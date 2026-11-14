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
```

`docker-compose.yml` runs the container as the host UID/GID and mounts
`./data`; make sure that directory is writable. For a read-only API deployment,
the container only needs read access to the SQLite file and its `-wal`/`-shm`
companions.

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
