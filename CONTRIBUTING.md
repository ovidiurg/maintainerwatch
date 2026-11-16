# Contributing

MaintainerWatch is a dual-use supply-chain research project. Contributions
must improve defensive review without publishing ranked target lists,
maintainer dossiers or offensive tooling.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Useful checks:

```bash
pytest
python -m compileall -q src scripts tests
pytest --cov=src/mw --cov-config=.coveragerc --cov-fail-under=75
make check
make docker-smoke
```

Run `make docker-smoke` before a PR touching `src/**`, `scripts/**`, the
Dockerfile, `docker-compose.yml`, `.dockerignore`, `pyproject.toml` or
`config/**`.

## Data and privacy

- Do not commit root `data/`, caches, reports, tokens or credentials.
- `src/mw/data/default.yaml` is tracked package data and must match
  `config/default.yaml`.
- Do not add maintainer email addresses, private data or malware samples.
- Validation labels must have a source URL, a pre-release cutoff and a clear
  review note. Historical labels belong in `validation/historical/`, not in the
  current-state cohort.
- Follow the dual-use and GDPR guidance in `docs/gdpr.md`.

## Model changes

For changes to weights or signals:

1. add or update tests;
2. keep the v2 test slice frozen;
3. run `mw calibrate --candidate ... --fail-on-regression`;
4. do not tune repeatedly on the same holdout;
5. bump `model_version` only after review and update validation configs.

OSV integration must follow the upstream
[`google/osv.dev/AGENTS.md`](https://github.com/google/osv.dev/blob/master/AGENTS.md):
use the schema/API, do not scrape the website, and follow upstream test and
generated-file rules if contributing there.

## Pull requests

Use the repository PR template. Add tests for behavior changes, update docs and
generated numbers, and report any known false positives or limitations.
