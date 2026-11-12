# Methodology

MaintainerWatch is an MVP for open, maintainer-level software supply-chain risk
intelligence. It is intentionally explainable and reproducible: every score can
be recomputed from stored signal values and evidence.

## Data sources (all public)

| Source | Used for |
|---|---|
| npm registry (`registry.npmjs.org`) | versions, `_npmUser`, `time`, provenance attestations |
| PyPI JSON API (`pypi.org/pypi/{name}/json`) | releases, upload times, signatures, author/maintainer |
| npm downloads API | weekly downloads |
| pypistats.org | weekly downloads |
| OSV (`api.osv.dev`) | vulnerability context |
| GitHub REST API | repo owner, owner account age, contributor share, commit emails |
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
improvement, not a takeover.

## Signals

| Signal | Weight | Definition |
|---|---|---|
| `publisher_change` | 30 | A canonical publisher identity changed between releases in the last 365 days. Value = min(1, changes / 2). |
| `bus_factor` | 20 | Share of repository contributions held by the top author (12 months). |
| `account_age` | 15 | Age of the repository owner account; younger is riskier. |
| `release_anomaly` | 15 | Dormancy followed by a release, or a burst of releases, from the release-time series. |
| `signing_gap` | 10 | Share of the latest 5 non-yanked releases without provenance/signatures. |
| `typosquat` | 10 | Damerau-Levenshtein distance 1 (or 2 for long names) to a top package, with low downloads. |

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

- PyPI does not expose a per-release publisher in its JSON API. For PyPI,
  `publisher_change` relies on maintainer snapshots captured over time; the
  first run has no history.
- npm exposes `_npmUser` per version, which gives a strong publisher history.
- GitHub commit-email matching depends on public commits and `.mailmap`
  coverage; many maintainers use noreply addresses.
- GitHub and Keybase coverage is partial. Missing data lowers confidence, not
  the score.
- Scores are risk indicators, not proof of compromise. They must be reviewed
  with the underlying evidence.

## Validation

The MVP replays known incidents (event-stream, ua-parser-js, colors, node-ipc,
PyPI `ctx`) against the data available before each incident and reports which
signals would have fired, together with false-positive rates on a sample of
popular packages.
