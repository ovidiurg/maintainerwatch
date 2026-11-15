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
- Bulk priority seeds are prepared by `scripts/prepare_npm_priority.py`,
  `scripts/prepare_pypi_priority.py`, `scripts/prepare_crates_priority.py` and
  `scripts/prepare_priority_seeds.py`; ingested data stays local.
- The project is dual-use: do not publish ranked target lists or maintainer
  dossiers; see the security/privacy sections in `README.md` and `docs/gdpr.md`.
- Current local baseline (15 Nov 2026): 13,646 packages (5,130 npm, 5,800 PyPI,
  2,350 crates, 301 Maven, 65 GitHub), app 0.4.14, model 0.5.2.

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
| Priority seed generation | `python scripts/prepare_npm_priority.py`; `python scripts/prepare_pypi_priority.py`; `python scripts/prepare_crates_priority.py` |
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
5. Run `python -m compileall -q src scripts tests`; check `mw --help` and the
   affected `mw COMMAND --help` output after CLI changes.
6. Update `README.md` / `INSTALL.md` / `docs/api.md` and all generated result
   numbers when commands, config, endpoints or metrics change.
7. Do not commit `data/`, caches, tokens or credentials.
8. For a public deployment, follow the dual-use and GDPR guidance; do not make
   automatic accusations about maintainers.

## OSV integration and upstream contributions

MaintainerWatch consumes the public OSV API and OSV-format records; it does not
modify `google/osv.dev`. If contributing upstream or extending the integration,
read and follow the upstream
[`AGENTS.md`](https://github.com/google/osv.dev/blob/master/AGENTS.md):

- use the OSV schema/API, not website scraping;
- follow Conventional Commits and the repository-specific test/lint commands;
- keep Go code behind the database interfaces required by the migration;
- never hand-edit generated files (`*_pb2.py`, `*.pb.go`, `queries.sql.go`,
  `schema_generated.json`);
- update the upstream `AGENTS.md` for major architectural or workflow changes.

## Environment variables

- `GITHUB_TOKEN` (or `gh auth token` fallback) and `GITLAB_TOKEN` for forge APIs.
- `MAINTAINERWATCH_API_KEY` for the read-only API (`X-API-Key`).
- `MAINTAINERWATCH_DYNAMIC_TOKEN` for the isolated dynamic worker.
- SMTP/alerts credentials belong in the environment, never in the repository.
