# High-band review — 21 Nov 2026

Model: `0.5.3`. This is a manual review of the **3 high-band packages with
substantial downloads that are not confirmed by an advisory**. The other 11
high-band packages are OSV-confirmed malicious packages.

The purpose is calibration review, not an accusation against the maintainers.

| Package | Score | Downloads/wk | OSV | Main high-band driver | Review status |
|---|---:|---:|---|---|---|
| `@cloudbase/wx-cloud-client-sdk` | 56.9 | 35,669 | none | repeated publisher changes; no repository URL | unverified |
| `libbz2-rs-sys` | 55.2 | 22,770,231 | none | maintainer turnover; deps.dev cooldown only | unverified |
| `caniuse-api` | 50.0 | 20,465,944 | none | publisher/email change, long release dormancy, signing gap | likely legitimate transfer; unverified |

## What the evidence says

- None of the three has a current-version advisory.
- All three enter the high band through publisher/continuity-style evidence,
  with `signing_gap` as corroboration.
- `@cloudbase` has no repository URL, so repository/commit context is absent.
- `caniuse-api` shows a long-lived package with a recent publisher change;
  that is a takeover *suspicion*, not proof.
- `libbz2-rs-sys` has maintainer turnover and a deps.dev cooldown finding, not
  an advisory.
- The current high-confidence rules discount some handovers, but not transfers
  where the old publisher is no longer present and the new publisher has not
  published this package before.

## Decision

No model change was made. These three must remain in a review queue, not be
used as malware labels. A future high-band precision change should require,
for high-download packages, an advisory or an independent behavioural/content
signal in addition to publisher change. That change must be evaluated on the
frozen v6 holdout before release.

## Next checks

1. Verify the package source/release diff and the publisher transfer through
   project channels.
2. Add matched controls or review notes before any weight change.
3. Re-run calibration against v6 only after labels are frozen.
