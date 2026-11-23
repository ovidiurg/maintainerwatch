# High-band review — 23 Nov 2026

Model: `0.5.3`. This is a manual review of the **6 high-band packages that are
not confirmed by a current-version advisory**. The other 11 high-band packages
are OSV-confirmed malicious packages.

The purpose is calibration review, not an accusation against the maintainers.

| Package | Score | Downloads/wk | OSV | Main high-band driver | Review status |
|---|---:|---:|---|---|---|
| `@cloudbase/wx-cloud-client-sdk` | 56.9 | 35,669 | none | repeated publisher changes; no repository URL | unverified |
| `pgpass` | 52.7 | 96,781,575 | none | publisher change; Scorecard available | unverified |
| `caniuse-api` | 50.3 | 20,465,944 | none | publisher/email change, long release dormancy, signing gap | likely legitimate transfer; unverified |
| `@apideck/better-ajv-errors` | 50.2 | 11,755,284 | none | publisher change; Scorecard available | unverified |
| `p-shells` | 53.7 | 13 | none | signing gap, commit anomaly, continuity | likely low-impact false-positive candidate; no advisory |
| `libbz2-rs-sys` | 51.4 | 22,770,231 | none | dependency risk, continuity, commit anomaly | likely legitimate crate; active foundation repo, no advisory |

## What the evidence says

- None of the six has a current-version advisory.
- The review cases enter the high band through publisher/continuity,
  repository, or dependency evidence rather than an advisory.
- `@cloudbase` has no repository URL, so repository/commit context is absent.
- `caniuse-api` shows a long-lived package with a recent publisher change;
  that is a takeover *suspicion*, not proof.
- `p-shells` has very low download volume and a small repository; its high band
  should not be read as a high-impact finding.
- `libbz2-rs-sys` has a large dependency footprint but an active foundation
  repository and recent commits; verify the dependency signal before treating
  it as package risk.
- The current high-confidence rules discount some handovers, but not transfers
  where the old publisher is no longer present and the new publisher has not
  published this package before.

## Decision

No model change was made. These six must remain in a review queue, not be
used as malware labels. A future high-band precision change should require,
for high-download packages, an advisory or an independent behavioural/content
signal in addition to publisher change. That change must be evaluated on the
frozen v6 holdout before release.

## Next checks

1. Verify the package source/release diff and the publisher transfer through
   project channels.
2. Add matched controls or review notes before any weight change.
3. Re-run calibration against v6 only after labels are frozen.
