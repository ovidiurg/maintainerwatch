# Installation

## Requirements

- Python 3.11 or newer
- pip and a virtual environment
- git
- Network access to npm, PyPI, crates.io, Maven Central, OSV and GitHub/GitLab
- Optional: the GitHub CLI (`gh`) for authenticated GitHub API calls

## Install from source

```bash
git clone https://github.com/ovidiurg/maintainerwatch.git
cd maintainerwatch

python3 -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

Without the development extras (no pytest):

```bash
pip install -e .
```

## GitHub authentication

GitHub's unauthenticated API limit is low. The tool uses, in order:

1. the `GITHUB_TOKEN` environment variable, or
2. the token from `gh auth token`, if the GitHub CLI is logged in.

Recommended:

```bash
gh auth login
# then simply run mw; the token is read at runtime and never stored
```

Alternative:

```bash
export GITHUB_TOKEN=...     # do not commit this
```

Verify that a token is detected (prints only a boolean):

```bash
python -c "from mw.config import load_config; print(bool(load_config().github_token))"
```

## Quick start

```bash
mw init
```

Small smoke test (no GitHub calls):

```bash
mw ingest --system npm --top 20 --no-github
mw score-all
mw scan lodash --system npm
```

A larger run:

```bash
mw ingest --system npm --top 200
mw ingest --system pypi --top 200
mw ingest --system crates --top 100
mw ingest --system maven --top 50
mw enrich-github --limit 100       # bounded repo stats, Scorecard and commits
mw enrich-impact --limit 500       # deps.dev dependent counts for impact ranking
mw backfill-osv --limit 500        # version-aware OSV affected ranges
mw backfill-deps
mw backfill-licenses
mw backfill-commits
mw backfill-snapshots
mw resolve --limit 150
mw score-all
mw report --out data/report.html
mw export --format parquet
mw export --format spdx
mw export --format cyclonedx
mw export --format osv
```

Maven uses a curated seed list by default; pass `--seed-file` with
`group:artifact` lines to target your own artifacts.

`enrich-github` only fills packages that do not have repository stats yet; use
`--limit` and `--pages` to bound GitHub requests. `backfill-commits` fetches the
last two GitHub commit pages per repository; for historical replay use `--until`
(see `scripts/incident_check.py`).
`backfill-snapshots` reconstructs PyPI maintainer snapshots from PEP 658
release metadata (or imports a JSONL/JSON/CSV file with `--source`).
GitLab forges are supported too: set `GITLAB_TOKEN` to raise the GitLab.com API
rate limit.

## Validation

Score and evaluate the committed validation dataset in a separate database:

```bash
mw score-all --config config/validation.yaml
mw evaluate-validation --config config/validation.yaml
# optional: --dataset validation/v1 --max-positives N --max-controls N
```

For the local obscure-package calibration sample, use
`config/validation-obscure.yaml`; the seed and builder scripts are
`scripts/prepare_obscure_controls.py` and `scripts/prepare_mvp_seeds.py`.

## Responsible use

MaintainerWatch is dual-use: its ranked maintainer/package risk view can also
lower the cost of offensive reconnaissance. Do not expose the raw database or a
public ranked target list. For a public API, use `MAINTAINERWATCH_API_KEY`, rate
limits, TLS and minimal logs. Exports exclude email addresses; keep raw caches
and SQLite access restricted. See the dual-use section in
[README.md](README.md) and [docs/gdpr.md](docs/gdpr.md).

## Alerts and REST API

```bash
mw alerts --min-score 40 --signal publisher_change --min-signal 0.5
mw alerts --min-score 50 --out data/alerts.json
mw alerts --rules --dry-run          # rules from config/default.yaml
mw alerts --rules --out data/alerts.json
mw serve --host 127.0.0.1 --port 8000
```

The API is read-only:

| Endpoint | Purpose |
|---|---|
| `GET /health` | status, app version and model version |
| `GET /systems` | package counts per ecosystem |
| `GET /packages?system=&band=&min_score=&min_dependents=&limit=&offset=` | paginated ranked packages |
| `GET /packages/{system}/{name}` | score, signals, context, dependencies, risk summary, impact |
| `GET /top?system=&limit=&offset=` | top risk |
| `GET /impact?system=&min_dependents=&limit=&offset=` | impact-ranked packages |
| `GET /alerts?min_score=&signal=&min_signal=` | ad-hoc alerts |
| `GET /alert-rules` | run configured rules without delivery |

Pagination uses the `X-Total-Count`, `X-Limit`, `X-Offset` and `X-Next-Offset`
headers. Run `mw enrich-impact --limit 500` to populate deps.dev dependent
counts used by `/impact` and the impact fields. Set `MAINTAINERWATCH_API_KEY` to require `X-API-Key`; set
`api.rate_limit_rpm` in the config to enable the in-memory rate limit. See
[docs/api.md](docs/api.md) for webhook/email delivery and examples.

## Where data lives

| Path | Contents |
|---|---|
| `data/maintainerwatch.sqlite` | packages, versions, maintainers, signals, scores |
| `data/cache/` | cached HTTP responses (short TTL) |
| `data/maintainerwatch-*.parquet` / `.csv` | exported datasets |
| `data/report.html` | static report |

`data/` is git-ignored. To start from scratch, remove
`data/maintainerwatch.sqlite` and run `mw init` again.

## Tests and checks

```bash
pytest
python -m compileall src
```

The test suite does not hit the network; it uses an in-memory SQLite database
and synthetic fixtures. `.github/workflows/ci.yml` runs it on Python 3.11–3.13
with a 75% core-code coverage gate and a secret scan.

## Packaging and operations

```bash
make install              # pip install -e ".[dev]"
make test
make lint                 # compileall
make build                # sdist + wheel in dist/
make check                # tests, build, validation check and twine check
make dataset-check        # validation/v1 schema and counts
make validation-sample    # validation/v1 seed files
make validation-eval      # evaluate config/validation.yaml
make validate             # incident replay report
./scripts/build_reproducible.sh
make docker               # docker build -t maintainerwatch:latest .
make docker-run           # run with ./data mounted on :8000
docker compose up -d --build
```

`mw maintain` is the cron-friendly post-ingest pipeline; `mw snapshot` records
the current maintainer snapshots. See [docs/operations.md](docs/operations.md)
for cron, systemd timer, Docker, backup and monitoring examples.

## Troubleshooting

- **GitHub 403 / rate limit** — run `gh auth login`, set `GITHUB_TOKEN`, or use
  `--no-github` (GitHub-based signals become not applicable).
- **Slow ingest** — the HTTP client is rate-limited (5 requests/second by
  default) and caches responses. Lower `http.rate_limit_qps` in
  `config/default.yaml` if a host throttles you.
- **PyPI package not found** — removed or renamed packages return no data; the
  ingest reports fewer packages than requested.
- **`mw: command not found`** — activate the virtual environment first.
- **Wrong Python version** — check `python --version`; 3.11+ is required.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
