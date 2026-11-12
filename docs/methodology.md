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
| Maven Central search API + POM | versions, license, SCM, developers, dependencies |
| npm downloads API | weekly downloads |
| pypistats.org | weekly downloads |
| OSV (`api.osv.dev`) | vulnerability context |
| GitHub REST API | repo owner, owner account age, contributor share, commit emails |
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
applicable until such a snapshot exists.

## Signals

| Signal | Weight | Definition |
|---|---|---|
| `publisher_change` | 30 | A canonical publisher identity changed between releases in the last 365 days. Value = min(1, changes / 2). |
| `bus_factor` | 20 | Share of repository contributions held by the top author (12 months). |
| `account_age` | 15 | Age of the repository owner account; younger is riskier. |
| `release_anomaly` | 15 | Dormancy followed by a release, or a burst of releases, from the release-time series. Not applicable for Maven, where release cadence is not assessed. |
| `signing_gap` | 10 | Share of the latest 5 non-yanked releases without provenance/signatures. Not applicable for crates.io/Maven (no signing data) or PyPI when no recent release is signed. |
| `typosquat` | 10 | Damerau-Levenshtein distance 1 (or 2 for long names) to a top package, with low downloads. |
| `license_inconsistency` | 5 | Missing, unknown, or non-SPDX license metadata. This is a metadata signal, not a legal audit. |

## Context

`scorecard_score` (OpenSSF Scorecard) and dependency counts are stored as
context, not part of the weighted score. `dependencies_count` is the number of
direct runtime/build dependencies of the latest ingested version; `fan_in` is
the number of ingested packages that depend directly on the package. Fan-in is
computed within the ingested sample, so it is a lower bound.

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
- License metadata prefers PyPI `license_expression` (PEP 639), but
  registry-vs-classifier and declared-vs-repository comparisons are still
  pending (see roadmap).
- npm exposes `_npmUser` per version, which gives a strong publisher history.
- GitHub commit-email matching depends on public commits and `.mailmap`
  coverage; many maintainers use noreply addresses.
- GitHub and Keybase coverage is partial. Missing data lowers confidence, not
  the score.
- Maven POMs may inherit licenses and dependencies from a parent POM. The MVP
  resolves parent POMs up to three levels for license/SCM, but some metadata can
  still be missing.
- `fan_in` counts direct dependents inside the ingested sample, not transitive
  dependents or the whole ecosystem.
- Scores are risk indicators, not proof of compromise. They must be reviewed
  with the underlying evidence.

## Validation

The MVP replays known incidents (event-stream, ua-parser-js, colors, node-ipc,
xz-utils) using data available before each incident.
`scripts/incident_check.py` writes `docs/incident-validation.md` with a
precision/recall table against a 27-package benign sample. The benign label is a
proxy, not ground truth. At threshold 40 the replay gives precision 0.222,
recall 0.400 and a false-positive rate of 0.259. The release-only replay misses
ua-parser-js (account hijack without a publisher change) and xz-utils
(commit-level takeover rather than a release anomaly).
