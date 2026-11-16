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
  `scripts/prepare_pypi_priority.py`, `scripts/prepare_crates_priority.py`,
  `scripts/prepare_maven_priority.py`, `scripts/prepare_github_priority.py`
  and `scripts/prepare_priority_seeds.py`; ingested data stays local.
- `src/mw/data/default.yaml` is tracked package data and must stay identical to
  `config/default.yaml`. The repository ignores only root `/data/`, not package
  data under `src/mw/data/`. `tests/test_versions.py` enforces this.
- Current checks: **187 tests**, coverage **76.20%**, CI green on Python 3.11–3.13; Docker smoke
  runs on relevant pull requests and on explicit manual dispatch only.
- The project is dual-use: do not publish ranked target lists or maintainer
  dossiers; see the security/privacy sections in `README.md` and `docs/gdpr.md`.
- Current local baseline (15 Nov 2026): 13,646 packages (5,130 npm, 5,800 PyPI,
  2,350 crates, 301 Maven, 65 GitHub), app 0.4.23, model 0.5.3.

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
curl 'http://127.0.0.1:8000/packages?band=high&limit=2'
curl 'http://127.0.0.1:8000/impact?limit=2'
curl 'http://127.0.0.1:8000/alerts?signal=osv_risk&min_signal=0.5&limit=2'
curl 'http://127.0.0.1:8000/alert-rules'
```

## Docker smoke test

The API container serves JSON only; the HTML report is a static file.

```bash
make docker-smoke
```

The script builds the image, checks `mw --help`, initialises a DB, generates a
report, renders `docker compose config`, starts the API and checks `/health` and
`/packages`. `make docker-report` is the report-only workflow.

Run Docker smoke before every PR that changes `src/**`, `scripts/**`,
`Dockerfile`, `docker-compose.yml`, `.dockerignore`, `pyproject.toml` or
`config/**`. CI runs it on relevant pull requests and when manually dispatched
with `docker_smoke=true`; normal pushes to `main` run the Python test matrix
only.

If Docker packaging changes, also verify that the wheel contains
`mw/data/default.yaml` and that `mw report` inside the container reports the
expected package count. Without a bind mount, copy the report out with
`docker cp <container>:/app/data/report.html ./report.html`; do not add it to
git.

## Common commands

| Goal | Command |
|---|---|
| Registry ingest | `mw ingest --system npm|pypi|crates|maven|github [--top N|--seed-file F] [--no-github]` |
| Full pipeline | `mw main [--top N] [--no-github] [--no-enrich]` |
| Recurring pipeline | `mw maintain [--limit N] [--no-export]` |
| Identity resolution | `mw resolve [--limit N]` |
| Priority seed generation | `python scripts/prepare_npm_priority.py`; `python scripts/prepare_pypi_priority.py`; `python scripts/prepare_crates_priority.py`; `python scripts/prepare_maven_priority.py`; `python scripts/prepare_github_priority.py` |
| Dependency/license/commit backfills | `mw backfill-deps`, `mw backfill-licenses`, `mw backfill-commits` |
| Impact data | `mw enrich-impact --limit N`; `mw prioritize-impact` |
| Advisory findings | `mw enrich-findings --limit N`; `mw backfill-osv --malicious-only` |
| Repository/Scorecard context | `mw enrich-github --limit N`; `mw enrich-scorecard --limit N` |
| Static content | `mw scan-content --limit N`; `mw scan-guarddog --limit N` |
| Isolated dynamic worker | `mw scan-dynamic --limit N` (requires `dynamic.worker_url`) |
| Score/search | `mw score-all`; `mw scan PACKAGE --system SYSTEM`; `mw alerts --min-score 40` |
| Validation | `mw evaluate-validation --config config/validation.yaml`; `mw evaluate-ablations --config config/validation.yaml`; `mw calibrate --candidate config/calibration-candidate.yaml`; `mw calibrate --search [--bootstrap 1000]`; `make calibration-loop` (baseline/drift only); `mw scan-diff --base origin/main --index dist/maintainerwatch-index.json`; `make ci-index`; `python scripts/calibration_drift.py` |
| Label intake | `python scripts/intake_osv_labels.py --input data/feedback/packages.jsonl` |
| Export/report/API | `mw export --format json|spdx|cyclonedx|osv`; `mw report`; `mw serve` |
| Docker report | `make docker-report`; `docker compose run --rm api mw report --out /app/data/report.html` |
| Privacy removal | `mw delete-package --system SYSTEM --name PACKAGE --yes` (dry-run without `--yes`) |

Use `mw --help` and `mw COMMAND --help` for the authoritative option list.

## Change checklist

1. Read the relevant source and docs before editing; follow existing style.
2. Add or update tests for behavior changes.
3. Run `pytest` and `python -m compileall -q src scripts tests`.
4. Run coverage with `pytest --cov=src/mw --cov-config=.coveragerc
   --cov-fail-under=75`.
5. Run `python -m compileall -q src scripts tests`; check `mw --help` and the
   affected `mw COMMAND --help` output after CLI changes. For calibration
   changes, run `mw calibrate --candidate config/default.yaml --out
   data/calibration.json` and confirm the guardrails pass.
6. Run `make docker-smoke` before a PR if the change touches `src/**`,
   `scripts/**`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`,
   `pyproject.toml` or `config/**`. Confirm the report path and API checks pass.
7. Keep `src/mw/data/default.yaml` in sync with `config/default.yaml`; update
   `model_version` in every validation config and bump the app version.
8. Update `README.md` / `INSTALL.md` / `docs/api.md`, AGENTS.md and all
   generated result numbers when commands, config, endpoints or metrics change.
9. Do not commit root `data/`, caches, report files, tokens or credentials.
10. For a public deployment, follow the dual-use and GDPR guidance; do not make
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
