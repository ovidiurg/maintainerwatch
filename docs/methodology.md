# Methodology

MaintainerWatch is an MVP for open, maintainer-level software supply-chain risk
intelligence. It is intentionally explainable and reproducible: every score can
be recomputed from stored signal values and evidence.

## Data sources (all public)

| Source | Used for |
|---|---|
| npm registry (`registry.npmjs.org`) | versions, `_npmUser`, `time`, provenance attestations |
| PyPI JSON API (`pypi.org/pypi/{name}/json`) | releases, upload times, signatures, author/maintainer |
| crates.io API (`crates.io/api/v1`) | crates, versions, owners, dependencies |
| Maven Central search API + `maven-metadata.xml` + POM | versions, license, SCM, developers, dependencies |
| npm downloads API | weekly downloads |
| pypistats.org | weekly downloads |
| OSV (`api.osv.dev`) | vulnerability context |
| GitHub REST API | repo owner, owner account age, contributor share, commit emails |
| GitHub commits API | commit authors and dates for `commit_anomaly` |
| keyserver.ubuntu.com (HKP) | GPG key IDs linked to publisher emails |
| GitHub releases API | release timeline for non-package projects such as xz |
| OpenSSF Scorecard | repository security score (context) |
| Keybase public API | self-declared identity proofs |

## Identity resolution

Signals about people are only meaningful if we know that two identities refer
to the same person. We store links in `identity_links` with a confidence:

- **high** — shared email (npm publisher email ↔ public commit email), shared
  GPG fingerprint, or a Keybase proof.
- **medium** — GitHub handle declared in package metadata, repository URL, or
  PyPI provenance.
- **low** — reserved for leads; never used in scoring.

`publisher_change` compares the canonical identity of the publisher between
consecutive releases. Links below the configured `min_identity_confidence`
(default `medium`) are ignored. Automation identities (npm OIDC trusted
publishing such as `npm-oidc-no-reply@github.com`, release bots, `+oss-bot`
aliases) are skipped, because a transition to automation is a security
improvement, not a takeover. For PyPI, crates.io and Maven, where a per-release
publisher is not available, the signal falls back to comparing current
maintainers with the oldest snapshot at least 180 days old; it stays not
applicable until such a snapshot exists. GPG keys are looked up on
keyserver.ubuntu.com by publisher email and accepted only when a UID matches;
all identity links are unioned per package, so two emails that share a key map
to the same canonical identity.

## Signals

| Signal | Weight | Definition |
|---|---|---|
| `publisher_change` | 30 | A canonical publisher identity changed between releases in the last 365 days. Value = min(1, changes / 2). |
| `bus_factor` | 20 | Share of repository contributions held by the top author (12 months). |
| `account_age` | 15 | Age of the repository owner account; younger is riskier. |
| `release_anomaly` | 15 | Dormancy followed by a release, or a burst of releases, from the release-time series. Not applicable for Maven, where release cadence is not assessed. |
| `signing_gap` | 10 | Share of the latest 5 non-yanked releases without provenance/signatures. Not applicable for crates.io/Maven (no signing data) or PyPI when no recent release is signed. |
| `typosquat` | 10 | Damerau-Levenshtein distance 1 (or 2 for long names) to a top package, with low downloads. |
| `license_inconsistency` | 5 | Missing, unknown, non-SPDX license metadata, or disagreement between the registry license, the PyPI classifier and the GitHub repository license. This is a metadata signal, not a legal audit. |
| `commit_anomaly` | 15 | New-author share in a 90-day window and commit burst (30 days vs the previous 90 days) from sampled GitHub commits. |
| `scorecard` | 10 | Low OpenSSF Scorecard repository score; value = max(0, (7 - score) / 7). |
| `dependency_risk` | 15 | Log-scaled transitive fan-in (200+ dependents = 1.0) plus a smaller fan-out component. |

## License sources

License metadata is cross-checked across sources: the registry license
(PyPI `license_expression`/`license` or the package field) against the PyPI
Trove classifier, and the declared license against the GitHub repository
license. Tokens are normalised to SPDX-like identifiers; compound licenses such
as `MIT OR Apache-2.0` are compatible when the other source matches any option.
Repository URLs are chosen from `project_urls`, excluding conduct, docs, issue
and wiki links and requiring a code-forge host; this prevents a "Code of
Conduct" URL from being mistaken for the source repository.

## Commit-level signal

`commit_anomaly` uses commits stored in the `commits` table (default: the last
two GitHub API pages, up to 200 commits per package; historical replay can fetch
commits before a cutoff with `mw backfill-commits --until`). It computes:
new-author share (commits in the last 90 days by authors first seen in the last
90 days, relative to all commits in the window) and commit burst (last 30 days
vs the average per 30 days over the previous 90 days, requiring at least 10
recent commits). The value is the maximum of the two components. The signal is
high-recall and low-precision: active projects can trigger it, so it is a
triage aid, not proof of compromise.

## Standard outputs

`mw export --format` writes `json` (full dataset with signals and context),
`spdx` (SPDX 2.3 JSON with purl external references), `cyclonedx` (CycloneDX
1.5 JSON BOM with risk properties) and `osv` (an OSV-compatible `results` array
of packages and vulnerability IDs), in addition to `parquet` and `csv`.

## Context

`scorecard_score` (OpenSSF Scorecard) is scored by the `scorecard` signal;
`dependencies_count` and `fan_in_transitive` feed `dependency_risk`.
`dependencies_count` is the number of direct runtime/build dependencies of the
latest ingested version. `fan_in` is the number of ingested packages that depend
directly on the package; `fan_in_transitive` is the number of distinct packages
that reach it through any dependency path inside the ingested graph
(cycle-safe). Both are lower bounds because only ingested packages are counted.
PyPI `requires_dist` entries gated by an `extra ==` marker (test/dev extras) are
excluded from the graph.

A signal that cannot be computed (for example, no repository data) is marked
`applicable = false` and excluded from the score rather than counted as zero.

## Score

```
score = 100 * sum(weight[s] * value[s]) / sum(weight[s])
```

over applicable signals. Bands: `< 25` low, `< 50` medium, otherwise high.
`inputs_hash` is the SHA-256 of the canonical JSON of applicable signal values,
evidence and model version, so a score can be verified.

## Limitations

- PyPI does not expose a per-release publisher in its JSON API.
  `publisher_change` falls back to the oldest maintainer snapshot at least 180
  days old; until such a snapshot exists, the signal is not applicable and
  PyPI scores use the remaining signals.
- `signing_gap` is not applicable for crates.io/Maven (no signing data) or PyPI
  when no recent release is signed, to avoid penalising ecosystems that do not
  use signatures.
- `release_anomaly` is not applicable for Maven: its release cadence (frequent
  batched releases, then long gaps) is not comparable to npm/PyPI and produced
  misleading anomalies.
- License metadata is cross-checked across registry, classifier and GitHub
  repository sources. Repository licenses come from GitHub's detection, which
  can differ from an individual package's license in a monorepo.
- npm exposes `_npmUser` per version, which gives a strong publisher history.
- GitHub commit-email matching depends on public commits and `.mailmap`
  coverage; many maintainers use noreply addresses.
- GitHub and Keybase coverage is partial. Missing data lowers confidence, not
  the score.
- Maven parsing resolves `${...}` property placeholders, built-in project
  properties and inherited parent properties; parents are followed up to six
  levels for license/SCM. BOM imports are detected but managed dependencies are
  not counted as direct edges, because they are not actual dependencies.
  Metadata can still be missing when a parent POM is absent or a license is
  only declared in a profile.
- `fan_in` is direct and `fan_in_transitive` adds reverse reachability; both
  count only the ingested graph, so they are lower bounds. PyPI test/dev extras
  are excluded.
- Commit history is sampled (default two pages); a long-term maintainer is not
  "new", and an account hijack that keeps the same author can still be missed.
- `commit_anomaly` is high-recall/low-precision and should be used as a triage
  aid, not as a standalone alarm.
- GPG coverage depends on keyserver publication and matching UIDs; missing keys
  are not a risk by themselves.
- `scorecard` and `dependency_risk` are not applicable when the repository or
  dependency data is absent.
- Publisher-level signing-key history is not implemented: npm signatures are
  registry-level, so the experimental `signing_key_change` signal is not
  weighted.
- Scores are risk indicators, not proof of compromise. They must be reviewed
  with the underlying evidence.

## Validation

The MVP replays known incidents (event-stream, ua-parser-js, colors, node-ipc,
xz-utils) using data available before each incident.
`scripts/incident_check.py` writes `docs/incident-validation.md` with a
precision/recall table against a 27-package benign sample. The benign label is a
proxy, not ground truth. At threshold 40 the replay gives precision 0.300,
recall 0.600 and a false-positive rate of 0.259. Commit-level signals catch the
ua-parser-js hijack burst and the xz-utils new-author/burst pattern; colors and
node-ipc remain medium at best.
