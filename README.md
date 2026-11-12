# MaintainerWatch

Open, cross-ecosystem **maintainer-level supply-chain risk intelligence**.

Current incidents (xz-utils, event-stream, ua-parser-js, colors) were not
CVE-driven: attackers gained control of package maintainership. Existing tools
describe packages (`deps.dev`), vulnerabilities (`OSV`) or repository practices
(`OpenSSF Scorecard`), but not the people behind packages across ecosystems.

MaintainerWatch ingests public package metadata, resolves maintainer identities
with explicit confidence levels, derives six explainable risk signals and
publishes a versioned open dataset plus a CLI/report.

## Scope

- Ecosystems: **npm**, **PyPI**, **crates.io** and **Maven Central** (top or
  seed lists), plus a **GitHub release timeline** for non-package projects.
- Signals:
  1. `publisher_change` — maintainer/publisher changed between releases
  2. `bus_factor` — concentration of commits in one author
  3. `account_age` — young maintainer account on a popular package
  4. `release_anomaly` — dormancy followed by a burst, or sudden release bursts
  5. `signing_gap` — missing provenance / signatures on recent releases
  6. `typosquat` — name close to a top package, with low downloads
  7. `license_inconsistency` — missing or non-SPDX license metadata
- Context: OSV vulnerabilities, OpenSSF Scorecard, dependency fan-in/out.
- Identity resolution (minimal, passive): Keybase proofs, GitHub commit
  emails / GPG keys, PyPI PEP 740 provenance. No social-media scraping.

## Install

See [INSTALL.md](INSTALL.md) for the full setup, GitHub authentication and
troubleshooting. Short version:

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
mw ingest --system crates --top 100
mw ingest --system maven --top 50
mw ingest --system github --top 1
mw backfill-deps
mw resolve
mw score-all

# Inspect one package.
mw scan requests --system pypi
mw scan event-stream --system npm
mw scan serde --system crates

# Alerts and the read-only API.
mw alerts --min-score 40 --signal publisher_change --min-signal 0.5
mw serve --host 127.0.0.1 --port 8000

# Export the dataset and build the report.
mw export --format parquet
mw report --out report.html
```

Data lives in `data/maintainerwatch.sqlite`; exports in `data/`.

Authentication: set `GITHUB_TOKEN`, or simply `gh auth login` once — the tool
falls back to `gh auth token` automatically.

## Results (MVP, 12 November 2026)

- 1,169 packages scored: 518 npm, 500 PyPI, 100 crates.io, 50 Maven and 1
  GitHub repository.
- 207,252 versions, 2,396 maintainers, 1,122 repositories, 3,229 OSV records,
  5,594 dependency edges.
- 2,034 identity links (1,211 high, 162 medium, 661 low confidence).
- Risk bands: 4 high, 429 medium, 736 low. OIDC/bot publishers are ignored.
- PyPI `publisher_change` is not applicable until 180 days of snapshot history
  exist; PyPI scores use the remaining signals until then.
- Highest: path-to-regexp 63.9, commander 52.5, express 51.4, antd 51.4.
- Pre-incident replay: event-stream 48.4, colors 40.0, node-ipc 38.0,
  ua-parser-js 0.0, xz-utils 18.9. At threshold 40 the 27-package benign
  sample gives precision 0.222, recall 0.400, false-positive rate 0.259.
- Pre-incident replay: event-stream 48.4, colors 40.0, node-ipc 38.0,
  ua-parser-js 0.0 (documented miss).

See [docs/nlnet-proposal.md](docs/nlnet-proposal.md) and
[docs/incident-validation.md](docs/incident-validation.md).

## Scoring

A weighted sum of applicable signals, normalised to 0–100, with an
`inputs_hash` for reproducibility. Every signal stores its evidence.
See [docs/methodology.md](docs/methodology.md) and
[docs/roadmap.md](docs/roadmap.md) for the model and remaining broader-scope
work.

## Ethics and privacy

Only public, role-related data is processed. Emails are stored hashed; the
public dataset contains package-level aggregates and evidence URLs, never
personal contact data. See [docs/gdpr.md](docs/gdpr.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
