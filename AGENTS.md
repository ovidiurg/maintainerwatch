# AGENTS.md — MaintainerWatch

Machine-oriented guide for AI coding agents working on this repository. The
human documentation remains authoritative: read `README.md`, `INSTALL.md`,
`docs/methodology.md`, `docs/api.md` and `docs/gdpr.md` before changing behavior.

## What this project is

MaintainerWatch is a Python 3.11+ CLI and read-only FastAPI service for
maintainer-level supply-chain risk intelligence. It ingests public registry
metadata into SQLite, computes explainable risk signals, and produces a scored
dataset, alerts, exports and an HTML report.

Key facts:

- CLI entry point: `mw` (`src/mw/cli.py`).
- Default database: `data/maintainerwatch.sqlite`.
- Default config: `config/default.yaml`; validation configs live in `config/`.
- Do not commit `data/`, caches, tokens or credentials.
- The project is dual-use: do not publish ranked target lists or maintainer
  dossiers; see the security/privacy sections in `README.md` and `docs/gdpr.md`.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Optional external tools are not required for the core CLI:

- `guarddog` for optional static scans (`pip install guarddog`);
- an isolated gVisor/Kata/Docker runner for `mw scan-dynamic`.

Never install or execute code from an untrusted package in the agent/analyst
process. `mw scan-content` and `mw scan-guarddog` are static. `mw scan-dynamic`
only calls a separately configured worker (`worker/README.md`).

## Smoke test

```bash
mw init
mw ingest --system npm --top 20 --no-github
mw score-all
mw scan lodash --system npm
mw report --out data/report.html
```

For API checks:

```bash
mw serve --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/packages?limit=2'
curl 'http://127.0.0.1:8000/impact?limit=2'
```

## Common commands

| Goal | Command |
|---|---|
| Registry ingest | `mw ingest --system npm|pypi|crates|maven|github [--top N|--seed-file F] [--no-github]` |
| Recurring pipeline | `mw maintain [--limit N] [--no-export]` |
| Identity resolution | `mw resolve [--limit N]` |
| Dependency/license/commit backfills | `mw backfill-deps`, `mw backfill-licenses`, `mw backfill-commits` |
| Impact data | `mw enrich-impact --limit N`; `mw prioritize-impact` |
| Advisory findings | `mw enrich-findings --limit N`; `mw backfill-osv --malicious-only` |
| Repository/Scorecard context | `mw enrich-github --limit N`; `mw enrich-scorecard --limit N` |
| Static content | `mw scan-content --limit N`; `mw scan-guarddog --limit N` |
| Isolated dynamic worker | `mw scan-dynamic --limit N` (requires `dynamic.worker_url`) |
| Score/search | `mw score-all`; `mw scan PACKAGE --system SYSTEM`; `mw alerts --min-score 40` |
| Validation | `mw evaluate-validation --config config/validation.yaml`; `mw evaluate-ablations --config config/validation.yaml` |
| Export/report/API | `mw export --format json|spdx|cyclonedx|osv`; `mw report`; `mw serve` |
| Privacy removal | `mw delete-package --system SYSTEM --name PACKAGE --yes` (dry-run without `--yes`) |

Use `mw --help` and `mw COMMAND --help` for the authoritative option list.

## Change checklist

1. Read the relevant source and docs before editing; follow existing style.
2. Add or update tests for behavior changes.
3. Run `pytest` and `python -m compileall -q src scripts tests`.
4. Run coverage with `pytest --cov=src/mw --cov-config=.coveragerc
   --cov-fail-under=75`.
5. Update `README.md` / `INSTALL.md` / `docs/api.md` when commands, config,
   endpoints or metrics change.
6. Do not commit `data/`, caches, tokens or credentials.
7. For a public deployment, follow the dual-use and GDPR guidance; do not make
   automatic accusations about maintainers.

## Environment variables

- `GITHUB_TOKEN` (or `gh auth token` fallback) and `GITLAB_TOKEN` for forge APIs.
- `MAINTAINERWATCH_API_KEY` for the read-only API (`X-API-Key`).
- `MAINTAINERWATCH_DYNAMIC_TOKEN` for the isolated dynamic worker.
- SMTP/alerts credentials belong in the environment, never in the repository.
