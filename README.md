# MaintainerWatch

Open, cross-ecosystem **maintainer-level supply-chain risk intelligence**.

Current incidents (xz-utils, event-stream, ua-parser-js, colors) were not
CVE-driven: attackers gained control of package maintainership. Existing tools
describe packages (`deps.dev`), vulnerabilities (`OSV`) or repository practices
(`OpenSSF Scorecard`), but not the people behind packages across ecosystems.

MaintainerWatch ingests public package metadata, resolves maintainer identities
with explicit confidence levels, derives six explainable risk signals and
publishes a versioned open dataset plus a CLI/report.

## Scope (MVP)

- Ecosystems: **npm** and **PyPI** (top packages).
- Signals:
  1. `publisher_change` — maintainer/publisher changed between releases
  2. `bus_factor` — concentration of commits in one author
  3. `account_age` — young maintainer account on a popular package
  4. `release_anomaly` — dormancy followed by a burst, or sudden release bursts
  5. `signing_gap` — missing provenance / signatures on recent releases
  6. `typosquat` — name close to a top package, with low downloads
- Identity resolution (minimal, passive): Keybase proofs, GitHub commit
  emails / GPG keys, PyPI PEP 740 provenance. No social-media scraping.

## Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# Ingest a small sample first (smoke test).
mw ingest --system npm --top 200

# Full configured run.
mw ingest --system npm
mw ingest --system pypi
mw resolve
mw score-all

# Inspect one package.
mw scan requests --system pypi
mw scan event-stream --system npm

# Export the dataset and build the report.
mw export --format parquet
mw report --out report.html
```

Data lives in `data/maintainerwatch.sqlite`; exports in `data/`.

Authentication: set `GITHUB_TOKEN`, or simply `gh auth login` once — the tool
falls back to `gh auth token` automatically.

## Scoring

A weighted sum of applicable signals, normalised to 0–100, with an
`inputs_hash` for reproducibility. Every signal stores its evidence.
See [docs/methodology.md](docs/methodology.md).

## Ethics and privacy

Only public, role-related data is processed. Emails are stored hashed; the
public dataset contains package-level aggregates and evidence URLs, never
personal contact data. See [docs/gdpr.md](docs/gdpr.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
