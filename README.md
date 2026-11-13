# MaintainerWatch

Open, cross-ecosystem **maintainer-level supply-chain risk intelligence**.

Current incidents (xz-utils, event-stream, ua-parser-js, colors) were not
CVE-driven: attackers gained control of package maintainership. Existing tools
describe packages (`deps.dev`), vulnerabilities (`OSV`) or repository practices
(`OpenSSF Scorecard`), but not the people behind packages across ecosystems.

MaintainerWatch ingests public package metadata, resolves maintainer identities
with explicit confidence levels, derives ten explainable risk signals and
publishes a versioned open dataset plus a CLI/report.

## Scope

- Ecosystems: **npm**, **PyPI**, **crates.io** and **Maven Central** (top or
  seed lists), plus a **GitHub/GitLab release timeline** for non-package
  projects.
- Signals:
  1. `publisher_change` — maintainer/publisher changed between releases
  2. `bus_factor` — concentration of commits in one author
  3. `account_age` — young maintainer account on a popular package
  4. `release_anomaly` — dormancy followed by a burst, or sudden release bursts
  5. `signing_gap` — missing provenance / signatures on recent releases
  6. `typosquat` — name close to a top package, with low downloads
  7. `license_inconsistency` — missing or non-SPDX license metadata
  8. `commit_anomaly` — new-author share and commit burst relative to the baseline
  9. `scorecard` — low OpenSSF Scorecard repository score
  10. `dependency_risk` — high transitive fan-in / dependency footprint
- Context: OSV vulnerability counts and the dependency graph.
- Identity resolution (minimal, passive): Keybase proofs, GitHub commit
  emails, GPG keyservers and PyPI PEP 740 provenance. No social-media scraping.

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
mw backfill-licenses
mw backfill-commits
mw backfill-snapshots
mw resolve
mw score-all

# Inspect one package.
mw scan requests --system pypi
mw scan event-stream --system npm
mw scan serde --system crates

# Alerts and the read-only API.
mw alerts --min-score 40 --signal publisher_change --min-signal 0.5
mw alerts --rules --dry-run
mw serve --host 127.0.0.1 --port 8000

# Export the dataset and build the report.
mw export --format parquet
mw export --format spdx
mw export --format cyclonedx
mw export --format osv
mw report --out report.html
```

See [docs/api.md](docs/api.md) for endpoints, pagination headers, the optional
`MAINTAINERWATCH_API_KEY`, rate limiting and alert-rule webhook/email delivery.
Alert rules and delivery targets live in `config/default.yaml` under `alerts`.

## Packaging and operations

```bash
make install          # editable install with dev extras
make test             # pytest
make build            # sdist + wheel
make check            # tests, build and twine check
./scripts/build_reproducible.sh   # builds twice and compares hashes
make docker           # container image
docker compose up -d --build      # serve on :8000 with ./data mounted
```

`mw maintain` runs the recurring post-ingest pipeline (backfills, identity
resolution, snapshots, scoring, exports and the report); `mw snapshot` records
just the current maintainer snapshots. `docs/operations.md` has cron, systemd
timer, Docker, backup and monitoring examples.

The calibration metadata lives in [`validation/v1/`](validation/README.md).
Rebuild with `python scripts/build_validation_dataset.py` and validate with
`python scripts/check_validation_dataset.py` (or `make dataset-check`).
A preliminary case-control evaluation on the validation database gives AUC
0.850, precision@25 0.96, and at threshold 40 precision 0.919 / recall 0.596 /
FPR 0.025. See [docs/validation/evaluation.md](docs/validation/evaluation.md).

For a release, run `make check` and upload with `twine upload dist/*`.

Data lives in `data/maintainerwatch.sqlite`; exports in `data/`.

Authentication: set `GITHUB_TOKEN`, or simply `gh auth login` once — the tool
falls back to `gh auth token` automatically. GitLab forges use `GITLAB_TOKEN`
(optional; public projects work without it, subject to rate limits).

## Results (MVP, 12 November 2026)

- 1,169 packages scored: 518 npm, 500 PyPI, 100 crates.io, 50 Maven and 1
  GitHub repository.
- 207,252 versions, 210,185 commits, 2,396 maintainers, 1,122 repositories,
  3,229 OSV records, 2,638 runtime dependency edges (PyPI extras excluded).
- 2,252 identity links (1,420 high, 162 medium, 670 low confidence).
- Risk bands: 1 high, 416 medium, 752 low. OIDC/bot publishers are ignored.
- License cross-check: 1,148 compatible/recognised, 10 non-SPDX, 7 missing and
  4 declared-vs-repository conflicts (pathspec, uvloop, eslint-visitor-keys,
  opencv-python-headless).
- Historical snapshots reconstructed from PyPI PEP 658 metadata for 224
  packages; PyPI `publisher_change` is now applicable (298 high, 20 low, 182
  not applicable) and its snapshot value is capped at 0.5.
- Highest: antd 50.0, editables 49.9, json5 47.4, aiohappyeyeballs 46.9,
  py 46.7, annotated-types 45.1, smallvec 44.9, path-to-regexp 44.3.
- Pre-incident replay: event-stream 59.5, colors 27.3, node-ipc 25.2,
  ua-parser-js 25.0, xz-utils 42.8. At threshold 40 the 27-package benign
  sample gives precision 0.333, recall 0.400, false-positive rate 0.148.
- Standard outputs: JSON, SPDX 2.3, CycloneDX 1.5 and OSV-compatible
  (`mw export --format json|spdx|cyclonedx|osv`).

See [docs/incident-validation.md](docs/incident-validation.md).

## Scoring

A weighted sum of applicable signals, normalised to 0–100, with an
`inputs_hash` for reproducibility. Every signal stores its evidence.
See [docs/methodology.md](docs/methodology.md) for the model.

## Ethics and privacy

Only public, role-related data is processed. Emails are stored hashed; the
public dataset contains package-level aggregates and evidence URLs, never
personal contact data. See [docs/gdpr.md](docs/gdpr.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
