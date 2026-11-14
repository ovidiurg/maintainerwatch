# MaintainerWatch

Open, cross-ecosystem **maintainer-level supply-chain risk intelligence**.

Current incidents (xz-utils, event-stream, ua-parser-js, colors) were not
CVE-driven: attackers gained control of package maintainership. Existing tools
describe packages (`deps.dev`), vulnerabilities (`OSV`) or repository practices
(`OpenSSF Scorecard`), but not the people behind packages across ecosystems.

MaintainerWatch ingests public package metadata, resolves maintainer identities
with explicit confidence levels, derives eleven explainable risk signals and
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
  11. `install_script` — suspicious npm install/postinstall content
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

Every command accepts `--config PATH` (default: `config/default.yaml`).
`mw --help` and `mw COMMAND --help` show the authoritative option list.
`mw init` creates an empty database; ingest/score/maintenance commands also
initialise the schema on first use. Read-only commands such as `scan` need an
ingested database.

```bash
# Smoke test: a small npm sample.
mw init
mw ingest --system npm --top 200
mw score-all
mw scan express --system npm
```

### Ingest and enrich

```bash
# Ingest registry metadata. Without --system, uses cfg.ecosystems.
mw ingest [--system npm|pypi|crates|maven|github] [--top N]
          [--seed-file FILE] [--github|--no-github] [--config PATH]

# Build a deterministic seed list instead of using a registry top-N.
# --seed-file is newline-separated; --github defaults to enabled.
mw ingest --system npm --seed-file data/mvp/seeds/npm.txt --no-github

# Fetch repo stats, OpenSSF Scorecard and bounded commit history for packages
# that do not have repo stats yet. Defaults: --limit 100, --pages 2.
mw enrich-github [--system SYSTEM] [--limit N] [--pages N] [--config PATH]

# Resolve maintainer identities (Keybase, GitHub email/GPG, PyPI provenance).
mw resolve [--limit N] [--config PATH]
```

### Backfills and recurring maintenance

```bash
# Dependency edges and fan-in.
mw backfill-deps [--system npm|pypi|crates|maven] [--limit N] [--config PATH]

# License classifiers and repository licenses; --refresh bypasses HTTP cache.
mw backfill-licenses [--system SYSTEM] [--limit N] [--refresh] [--config PATH]

# GitHub/GitLab commits; --until limits historical replay, --pages is 100/page.
mw backfill-commits [--system SYSTEM] [--name PACKAGE] [--until ISO_DATE]
                    [--pages N] [--limit N] [--config PATH]

# Import a JSONL/JSON/CSV snapshot, or reconstruct PyPI snapshots.
mw backfill-snapshots [--source FILE] [--limit N] [--config PATH]

# Record the current maintainer set as a snapshot.
mw snapshot [--system SYSTEM] [--limit N] [--config PATH]

# Full recurring pipeline: backfills, identities, snapshots, scores, exports.
mw maintain [--with-commits|--no-with-commits] [--limit N]
            [--export|--no-export] [--config PATH]
```

### Score, inspect and alert

```bash
mw score-all [--config PATH]

# Name is positional; --system accepts npm, pypi, crates, maven or github.
mw scan PACKAGE [--system|-s SYSTEM] [--config PATH]

# Simple threshold list, or config-driven rules with webhook/email delivery.
mw alerts [--min-score 40] [--signal SIGNAL] [--min-signal 0.5] [--limit N]
          [--rules] [--webhook URL] [--email ADDRESS] [--dry-run]
          [--out FILE] [--config PATH]

# Read-only REST API.
mw serve [--host 127.0.0.1] [--port 8000] [--config PATH]
```

`mw alerts --rules` uses the `alerts.rules` block in `config/default.yaml`.
`--dry-run` matches rules without delivering; `--out` writes JSON.
See [docs/api.md](docs/api.md) for endpoints, pagination, `MAINTAINERWATCH_API_KEY`
and rate limiting.

### Validation

```bash
# Score and evaluate the committed case-control dataset.
mw score-all --config config/validation.yaml
mw evaluate-validation --config config/validation.yaml
# Options: --dataset validation/v1 --max-positives N --max-controls N

# Obscure-package calibration sample (data/ is local, not committed).
python scripts/prepare_obscure_controls.py
python scripts/prepare_mvp_seeds.py
mw init --config config/validation-obscure.yaml
mw ingest --system npm --seed-file data/validation-obscure/seeds/npm-all.txt \
          --no-github --config config/validation-obscure.yaml
mw score-all --config config/validation-obscure.yaml
```

`make validation-sample` builds `validation/v1` seed files;
`make validation-eval` evaluates the validation config;
`make dataset-check` validates the committed dataset metadata.

### Export, report and packaging

```bash
mw export [--format parquet|csv|json|spdx|cyclonedx|osv] [--config PATH]
mw report [--out report.html] [--config PATH]
```

`mw export` writes under the configured `data_dir`; `mw report` builds a static
HTML report. Rows with medium/high scores include a short risk type, description
and next investigation step. Standard outputs are JSON, SPDX 2.3, CycloneDX 1.5
and OSV-compatible JSON.

### Make targets

```bash
make install             # editable install with dev extras
make install-release     # add release/build extras
make test                # pytest
make lint                # compileall
make build               # sdist + wheel
make check               # tests, build, dataset check and twine check
make dataset-check       # validation/v1 schema and counts
make validation-sample   # validation/v1 seed files
make validation-eval     # evaluate config/validation.yaml
make validate            # incident replay report
make maintain            # mw maintain
make snapshot            # mw snapshot
make docker              # build container image
make docker-run          # run container with ./data mounted on :8000
make clean               # remove build artifacts
```

Authentication is read from `GITHUB_TOKEN`/`GITLAB_TOKEN`, with automatic
fallback to `gh auth token`; `MAINTAINERWATCH_API_KEY` protects the API.

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
0.849, precision@25 1.0, and at threshold 40 precision 0.932 / recall 0.605 /
FPR 0.021. See [docs/validation/evaluation.md](docs/validation/evaluation.md).

For a release, run `make check` and upload with `twine upload dist/*`.

Data lives in `data/maintainerwatch.sqlite`; exports in `data/`.

Authentication: set `GITHUB_TOKEN`, or simply `gh auth login` once — the tool
falls back to `gh auth token` automatically. GitLab forges use `GITLAB_TOKEN`
(optional; public projects work without it, subject to rate limits).

## Results (MVP, 13 November 2026)

- 1,713 packages scored: 908 npm, 533 PyPI, 191 crates.io, 80 Maven (30 of 124 expansion seeds)
  and 1 GitHub repository. The expansion adds 544 registry-metadata packages across
  ecosystems, mixing popular and obscure packages.
- 231,281 versions, 221,675 commits, 3,524 maintainers, 1,212 repositories,
  3,286 OSV records, 3,940 runtime dependency edges (PyPI extras excluded).
- 2,252 identity links (1,420 high, 162 medium, 670 low confidence).
- Risk bands: 1 high, 407 medium, 1,305 low. OIDC/bot publishers are ignored.
- License cross-check: 1,652 compatible/recognised, 13 non-SPDX, 43 missing and
  4 declared-vs-repository conflicts.
- Historical snapshots reconstructed from PyPI PEP 658 metadata for 224
  packages; PyPI `publisher_change` is now applicable (298 high, 20 low, 182
  not applicable) and its snapshot value is capped at 0.5.
- Highest risk scores: jeepney 51.4 (single-maintainer concentration and
  dormancy, not a malware label), bincode 48.5, b-plus-tree-ts 48.0,
  b-side 48.0, py 46.7, proc-macro2 45.2, configparser 45.2.
- Pre-incident replay: event-stream 59.0, colors 27.3, node-ipc 24.1,
  ua-parser-js 25.0, xz-utils 39.3. At threshold 40 the 27-package benign
  sample gives precision 0.333, recall 0.400, false-positive rate 0.148.
- Validation sample: 69 of 114 known positives at threshold 40 (precision
  0.932, FPR 0.021); 44 at threshold 50. The main MVP DB has no labelled
  positives; validation is the true-positive evidence.
- GitHub enrichment covered the 100 highest-risk unenriched packages: 80
  repositories and 11,443 commits, with a bounded two-page commit window.
  Install-script scanning found 180 npm packages with install scripts; none
  reached the high-risk pattern band (core-js is medium at 0.5).
- Bulk package ingestion used `--no-github`, so new metadata did not trigger
  GitHub requests. SQLite is 175 MB and the request cache is 3.0 GB.
- Standard outputs: JSON, SPDX 2.3, CycloneDX 1.5 and OSV-compatible
  (`mw export --format json|spdx|cyclonedx|osv`).

See [docs/incident-validation.md](docs/incident-validation.md).

## Scoring

A weighted sum of applicable signals, normalised to 0–100, with an
`inputs_hash` for reproducibility. Every signal stores its evidence.
`mw scan` also reports `evidence_coverage`; low-coverage, hygiene-only scores
are review candidates rather than confirmed high risk. High-band scores are
reserved for packages with behavioural evidence; obscure low-adoption packages
use a medium-capped unsigned baseline.
See [docs/methodology.md](docs/methodology.md) for the model.

## Ethics and privacy

Only public, role-related data is processed. The local database can contain
public registry and commit email fields; those fields are not included in the
exported dataset. Before any public deployment, hash or minimise email
addresses, restrict access to the raw database, and complete the assessment in
[docs/gdpr.md](docs/gdpr.md).

## Dual-use and responsible use

MaintainerWatch is **dual-use**. It produces a ranked, explainable view of
maintainer and package risk from public metadata. The same ranking that helps a
security team triage a dependency can also lower the cost of offensive
reconnaissance: target selection for account takeover or social engineering,
identifying dormant or single-maintainer projects, typosquatting and
dependency-confusion planning, or mapping maintainer identities.

The project deliberately does **not** include exploits, credentials, private
data, breach data or automated attack tooling. A high score is a request for
review, not proof of compromise and not a claim that a package is “attackable”.
The report therefore pairs each medium/high score with a short risk type and a
defensive next step.

Responsible use expectations:

- Prefer a local or access-controlled deployment; protect the REST API with
  `MAINTAINERWATCH_API_KEY`, rate limits and a reverse proxy.
- Do not publish ranked target lists, maintainer dossiers or raw databases.
  Publish aggregate findings only when necessary, with identities minimised.
- Keep exported datasets free of personal contact data; hash or remove email
  addresses before sharing. Apply retention limits to raw caches.
- Use findings for defence, maintenance and coordinated disclosure. Do not
  make automated accusations about individuals or harass maintainers.
- If you deploy a public instance, add terms of use, access logging that
  minimises personal data, and a data-protection review.

If you are a maintainer and want a link or record corrected or removed, see the
contact process in [docs/gdpr.md](docs/gdpr.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
