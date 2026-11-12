# Installation

## Requirements

- Python 3.11 or newer
- pip and a virtual environment
- git
- Network access to npm, PyPI, OSV and GitHub
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
mw backfill-deps
mw resolve --limit 150
mw score-all
mw report --out data/report.html
mw export --format parquet
```

Maven uses a curated seed list by default; pass `--seed-file` with
`group:artifact` lines to target your own artifacts.

## Alerts and REST API

```bash
mw alerts --min-score 40 --signal publisher_change --min-signal 0.5
mw alerts --min-score 50 --out data/alerts.json
mw serve --host 127.0.0.1 --port 8000
```

The API is read-only:

| Endpoint | Purpose |
|---|---|
| `GET /health` | status and model version |
| `GET /systems` | package counts per ecosystem |
| `GET /packages?system=&band=&min_score=&limit=` | ranked packages |
| `GET /packages/{system}/{name}` | score, signals, context, dependencies |
| `GET /top?system=&limit=` | top risk |
| `GET /alerts?min_score=&signal=&min_signal=` | threshold alerts |

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
and synthetic fixtures.

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
