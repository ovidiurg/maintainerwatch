# MaintainerWatch

Open-source **research preview** for cross-ecosystem **maintainer-level
supply-chain risk intelligence**.

MaintainerWatch performs **static analysis of public package metadata and
bounded package archives**. It is a defensive research tool, not a production
detector, and it never executes untrusted package code in the analyst process.

Current incidents (xz-utils, event-stream, ua-parser-js, colors) were not
CVE-driven: attackers gained control of package maintainership. Existing tools
describe packages (`deps.dev`), vulnerabilities (`OSV`) or repository practices
(`OpenSSF Scorecard`), but not the people behind packages across ecosystems.

MaintainerWatch ingests public package metadata, resolves maintainer identities
with explicit confidence levels, derives fourteen explainable risk signals and
publishes a versioned open dataset plus a CLI/report.

## For AI agents

See [AGENTS.md](AGENTS.md) for a machine-oriented quick guide: safe install,
smoke test, command map, validation/coverage checks, data-handling rules and the
boundary that untrusted package code must only run in an isolated dynamic
worker.

## Who is it for

- **Open-source maintainers** who want an early, explainable signal that a
  project’s release or maintainer activity has changed.
- **Application security and supply-chain teams** triaging dependencies before
  adoption, upgrades or incident response.
- **Platform and CI/CD engineers** who need a local, read-only inventory signal
  without sending package metadata to a SaaS service.
- **Researchers and policy teams** studying maintainer concentration,
  takeover patterns and registry hygiene with reproducible, versioned data.
- **Not** an automated blocking system, malware verdict engine or target list.
  A high score is a review request; a low score is not proof of safety.

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
  6. `typosquat` — name close to a top package (homoglyphs and keyboard-adjacent typos), with low downloads
  7. `license_inconsistency` — missing or non-SPDX license metadata
  8. `commit_anomaly` — new-author share and commit burst relative to the baseline
  9. `scorecard` — low OpenSSF Scorecard repository score
  10. `dependency_risk` — high transitive fan-in / dependency footprint
  11. `osv_risk` — version-aware MAL/CVE advisory affecting the current release
  12. `depsdev_findings` — version-aware malicious/deprecated/low-usage findings
  13. `maintainer_continuity` — recent author handover or newcomer dominance
  14. `install_script` — suspicious npm install/postinstall content
- Context: OSV vulnerability counts and the dependency graph.
- Identity resolution (minimal, passive): Keybase proofs, GitHub commit
  emails, GPG keyservers and PyPI PEP 740 provenance. No social-media scraping.

## Quick start

### 1. Install from the repository

The package is installed from the checkout (it is not yet published on PyPI):

```bash
git clone https://github.com/ovidiurg/maintainerwatch.git
cd maintainerwatch
python -m venv .venv
. .venv/bin/activate
pip install .
```

For development use `pip install -e ".[dev]"`; see [INSTALL.md](INSTALL.md) for
GitHub authentication and troubleshooting.

### 2. Run the complete pipeline

```bash
mw main --top 5000 --no-github
```

That single command initialises the database, ingests npm/PyPI metadata,
enriches it, computes signals and scores, exports all formats, builds
`data/report.html`, and writes the compact PR/CI index.

For a minimal/offline run:

```bash
mw main --top 50 --no-github --no-enrich --no-export
```

No calibration step is needed: `mw main` uses the published, already-calibrated
model. Calibration is a maintainer release activity, not an installation step.

### 3. Open the results

```bash
xdg-open data/report.html
# or:
python3 -m http.server 8080 --directory data

mw scan express --system npm
mw serve --host 127.0.0.1 --port 8000
```

Outputs live under `data/`; the current dataset snapshot and validation
numbers are in the Results section below.

Every command accepts `--config PATH` (default: `config/default.yaml`).
`mw --help` and `mw COMMAND --help` show the authoritative option list.
`mw init` creates an empty database; ingest/score/maintenance commands also
initialise the schema on first use. Read-only commands such as `scan` need an
ingested database.

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

# Fetch deps.dev dependent counts for high-download packages.
mw enrich-impact [--system SYSTEM] [--limit N] [--config PATH]

# Fetch deps.dev findings (MALICIOUS/DEPRECATED/LOW_USAGE/etc.).
mw enrich-findings [--system SYSTEM] [--limit N] [--config PATH]

# Fetch individual OpenSSF Scorecard checks for existing repositories.
mw enrich-scorecard [--system SYSTEM] [--limit N] [--config PATH]

# Statically scan package tarballs for risky content.
mw scan-content [--system SYSTEM] [--min-score 40] [--limit N] [--dry-run]

# Optional GuardDog static analysis (pip install guarddog).
mw scan-guarddog [--system npm|pypi] [--min-score 40] [--limit N]

# Send selected packages to an isolated dynamic worker (configure dynamic.worker_url).
mw scan-dynamic [--system npm|pypi] [--min-score 40] [--limit N]

# Fetch affected-version ranges for OSV advisories (version-aware signal).
mw backfill-osv [--system SYSTEM] [--limit N] [--malicious-only] [--config PATH]

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
See [docs/api.md](docs/api.md) for endpoints, pagination, impact ranking,
`MAINTAINERWATCH_API_KEY` and rate limiting. `GET /impact` orders packages by
deps.dev dependents, downloads and transitive fan-in; run `mw enrich-impact`
first.

### Validation

```bash
# Score and evaluate the committed case-control dataset.
mw score-all --config config/validation.yaml
mw evaluate-validation --config config/validation.yaml
# Options: --dataset validation/v1 --max-positives N --max-controls N
#          --since ISO_DATE --until ISO_DATE (temporal positive slice)

# Leave-one-signal-out metrics; always pass the validation config.
mw evaluate-ablations --config config/validation.yaml --out data/ablations.json

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
mw calibrate --candidate config/calibration-candidate.yaml [--fail-on-regression]
mw calibrate --search [--search-max 80] [--bootstrap 1000]
mw scan-diff --base origin/main --index dist/maintainerwatch-index.json --format sarif
```

`mw export` writes under the configured `data_dir`; `mw report` builds a static
HTML report. `mw calibrate` compares candidate weights against the baseline on
the temporal validation samples; see [`docs/calibration.md`](docs/calibration.md).

Rows with medium/high scores include a short risk type, description
and next investigation step; impact is shown separately as deps.dev dependent
count plus a tier (low/medium/high/critical). Standard outputs are JSON, SPDX 2.3, CycloneDX 1.5
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

CI runs the test suite on Python 3.11–3.13, including API tests, compileall and
secret scanning. Coverage is enforced at 75% over the core model/API code; the
network ingestion adapters and CLI entrypoint are excluded from the coverage
denominator. Docker smoke runs on pull requests that touch code, Docker,
`pyproject.toml`, `docker-compose.yml` or `config/`, and on manual
`workflow_dispatch` with `docker_smoke=true`.

Authentication is read from `GITHUB_TOKEN`/`GITLAB_TOKEN`, with automatic
fallback to `gh auth token`; `MAINTAINERWATCH_API_KEY` protects the API.

## Project page

A static landing page lives in [`site/`](site/) and is deployed by
`.github/workflows/pages.yml` to GitHub Pages. After making the repository
public, enable **Settings → Pages → Build and deployment → Source: GitHub
Actions**. The expected URL is:

`https://ovidiurg.github.io/maintainerwatch/`

The page is self-contained and contains no local data or maintainer dossiers.
Preview locally with `python -m http.server --directory site 8000`.

## Packaging and operations

```bash
make install          # editable install with dev extras
make test             # pytest
make build            # sdist + wheel
make check            # tests, build and twine check
./scripts/build_reproducible.sh   # builds twice and compares hashes
make docker           # container image
docker compose up -d --build      # serve on :8000 with ./data mounted
make docker-report    # write ./data/report.html from the container
make main            # full pipeline: ingest, enrich, score, export, report
make calibration      # compare candidate weights with the baseline
make calibration-search # explicit search; not part of the daily loop
make calibration-loop   # baseline history + drift, without retuning
make ci-index           # build compact PR/CI risk index
make ci-publish-index   # publish versioned + latest index to GitHub Releases
make calibration-drift # render append-only calibration history
make label-intake      # collect candidate OSV MAL labels for review
```

Docker report workflow:

```bash
# Rebuild scores/report with the database mounted at ./data.
docker compose run --rm api mw report --out /app/data/report.html

# The file is then on the host:
ls -lh data/report.html
xdg-open data/report.html    # or open it in a browser

# If you prefer HTTP instead of file://:
python3 -m http.server 8080 --directory data
# http://127.0.0.1:8080/report.html
```

The API does not serve the static HTML report; generate it into `/app/data`
(the compose bind mount) and open it from the host, or serve `data/` with a
static file server. `mw maintain` also writes `data/report.html` when run
inside the compose volume.

`mw maintain` runs the recurring post-ingest pipeline (backfills, identity
resolution, snapshots, scoring, exports and the report); `mw snapshot` records
just the current maintainer snapshots. `docs/operations.md` has cron, systemd
timer, Docker, backup and monitoring examples.

The calibration metadata lives in [`validation/v1/`](validation/README.md).
Rebuild with `python scripts/build_validation_dataset.py` and validate with
`python scripts/check_validation_dataset.py` (or `make dataset-check`).
Calibration is performed by maintainers once per model release, against the
temporal holdout. End users do not need validation databases or a calibration
step; `mw main` uses the published, already-calibrated model.

A preliminary case-control evaluation on the validation database gives AUC
0.875, PR-AUC 0.855, Brier 0.1164, precision@25 1.0, and at threshold 40
precision 0.973 / recall 0.632 / FPR 0.008. See [docs/validation/evaluation.md](docs/validation/evaluation.md).
A larger, year-stratified, non-OSV sample (`config/validation-v2.yaml`) gives
489 positives / 1,008 controls, AUC 0.891, threshold-40 precision 0.970 /
recall 0.671 / FPR 0.010; the 2026 test slice is 0.969 precision / 0.851 recall,
while the small pre-2026 train slice remains weak. See [docs/validation/evaluation-v2.md](docs/validation/evaluation-v2.md).

For a release, run `make check` and upload with `twine upload dist/*`.

Data lives in `data/maintainerwatch.sqlite`; exports in `data/`.

Authentication: set `GITHUB_TOKEN`, or simply `gh auth login` once — the tool
falls back to `gh auth token` automatically. GitLab forges use `GITLAB_TOKEN`
(optional; public projects work without it, subject to rate limits).

## Results (MVP, 15 November 2026 · app 0.4.23 · model 0.5.3)

- 13,646 packages scored: 5,130 npm, 5,800 PyPI, 2,350 crates.io, 301 Maven
  and 65 GitHub repositories. The expansion mixes high-usage packages,
  transitive dependencies and a usage-stratified obscure sample.
- 1,413,269 versions, 243,608 commits, 22,653 maintainers, 1,375 repositories,
  10,014 OSV records, 47,443 runtime dependency edges (PyPI extras excluded).
- 2,252 identity links (1,420 high, 162 medium, 670 low confidence).
- Risk bands: 7 high, 3,124 medium, 10,515 low. OIDC/bot publishers are ignored.
- License metadata is cross-checked across registry, classifier and repository
  sources.
- Historical snapshots reconstructed from PyPI PEP 658 metadata for 224
  packages; PyPI `publisher_change` uses a capped snapshot value.
- deps.dev impact enrichment covers 869 packages. Top impact: tslib 1.62M
  dependents, inherits 1.33M, function-bind 1.30M, es-errors 1.26M, hasown 1.24M.
- Highest numerical scores include obscure low-adoption packages (`b.js`, `4a`,
  `b4`, `b5`, `b7` at 68.0 and `p-resolver`/`p01` at 88.0); they are capped to
  medium without behavioural/advisory evidence and remain triage candidates,
  not malware labels. `pypi/langchain-ai` reaches 100 but remains medium
  because its evidence is name-similarity/hygiene, not a confirmed compromise.
- Pre-incident replay (19 incidents): event-stream 65.6 high;
  eslint-config-prettier 56.4 high; xz-utils 44.8 medium; ua-parser-js 27.3;
  colors 22.7; node-ipc 20.6; the 2025 npm phishing and 2026 ChainDrop packages
  are mostly low, and same-account hijacks remain a blind spot. At threshold 40
  the 46-package benign replay sample gives precision 0.273, recall 0.158,
  false-positive rate 0.174 — replay remains a diagnostic, not a production
  detector. A sensitivity run that adds `maintainer_continuity`
  to replay (weight 15) moves ua-parser-js from 27.3 to 40.7 without adding a
  benign package above 40; the 19-incident sample is still too small to treat
  this as a stable production threshold.
- External cross-check of the current high band (OSV plus deps.dev) confirms
  all **7/7** high packages as malicious. A same-author release burst had
  incorrectly promoted `crates/num_threads` to high; the high-confidence gate
  now requires new-author evidence, so it is medium at 51.4 (evidence-only).
  None of the seven npm high packages has Sigstore/Rekor provenance, so the
  validation is advisory-based rather than signature-based.
- Validation v2 sample: 328 of 489 known positives at threshold 40 (precision
  0.970, FPR 0.010); 327 at threshold 50. High-band precision is 1.0, but
  high-band recall is deliberately conservative; see
  [docs/validation/evaluation-v2.md](docs/validation/evaluation-v2.md).
- GitHub enrichment is impact-ranked and bounded: the latest pass covered 90
  repositories and 11,335 commits with a two-page commit window.
  Install-script scanning flags only high-risk npm install scripts.
- Bulk package ingestion used `--no-github`; SQLite is 800 MB and the request
  cache is 7.2 GB.
- Standard outputs: JSON, SPDX 2.3, CycloneDX 1.5 and OSV-compatible
  (`mw export --format json|spdx|cyclonedx|osv`).

See [docs/incident-validation.md](docs/incident-validation.md) and
[docs/pr-ci.md](docs/pr-ci.md) for the dependency-diff/SARIF integration.

## Scoring

A weighted sum of applicable signals, normalised to 0–100, with an
`inputs_hash` for reproducibility. Every signal stores its evidence.
`mw scan` also reports `evidence_coverage`; low-coverage, hygiene-only scores
are review candidates rather than confirmed high risk. High-band scores are
reserved for packages with high-confidence behavioural/advisory evidence
(`publisher_change`, `commit_anomaly`, `osv_risk`, `depsdev_findings`,
`install_script`, `maintainer_continuity`); `commit_anomaly` also needs
new-author evidence, so a same-author release burst alone does not grant the
high band. On GitHub and Maven, publisher/commit changes alone do not qualify;
an advisory/content signal is required. Other high numerical scores are kept at
medium. Obscure low-adoption packages use a medium-capped unsigned
baseline. `scan`/API also expose maintainer count,
commit-author count/span, GuardDog findings and static content flags as context. Repository metadata (archived, owner
type, stars/forks/issues), individual Scorecard checks and static tarball scan
flags are exposed as context in `scan`/API; scored `repo_health`/content
experiments are not in the model because the validation gain was not safe.
GuardDog results are optional context too (`guarddog_risk_score`,
`guarddog_findings`). Dynamic execution is delegated to `worker/` and runs only
in an isolated gVisor/Docker sandbox; it is never executed in the analyst
process. Set `dynamic.worker_url` and run the worker separately.
**Known blind spots:** if a maintainer account is compromised but the attacker
publishes under the *same publisher identity*, MaintainerWatch may not see a
control change. `publisher_change` stays zero and the replay score can remain
low even when the release is malicious. Documented examples: release-only
replay leaves `ua-parser-js` at 27.3; adding `maintainer_continuity` raises it
to 40.7, while `eslint-scope`, `eslint-config-eslint`, `coa` and `rc` remain
low.
Other blind spots: long-term maintainer social engineering (`xz`), removed or
renamed packages with no usable history, attacks outside package registries
(CI actions/build systems), and the absence of dynamic execution in the analyst
process. A low score is not a claim that a package is safe; see
[docs/incident-validation.md](docs/incident-validation.md).

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

## Contact

We intentionally do **not** publish a general contact email address, to reduce
spam and unsolicited bulk mail. Use these channels instead:

- **Privacy, correction or removal requests:** GitHub private security advisory
  (`https://github.com/ovidiurg/maintainerwatch/security/advisories/new`).
- **Security reports:** the same private advisory channel; do not disclose
  vulnerabilities in a public issue.
- **General questions and bugs:** GitHub Issues.

For a local deployment, remove a package and its versions, maintainers,
signals, scores, snapshots, commits, OSV rows, repository stats, dependencies
and identity links with:

```bash
mw delete-package --system SYSTEM --name PACKAGE --yes
```

See [docs/gdpr.md](docs/gdpr.md) for the full removal process.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development, testing, model
calibration and privacy rules, and [SECURITY.md](SECURITY.md) for private
vulnerability reporting. Public-release preparation is tracked in
[docs/public-release.md](docs/public-release.md).

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
