# High-band review — 24 Nov 2026

Generate the current review packet with:

```bash
make high-band-review
# writes data/reviews/high-band-YYYYMMDD.{json,md}
```

Model: `0.5.3`. This is a manual review of the **10 high-band packages not
confirmed malicious by MAL/deps.dev**. Thirteen high-band packages are MAL or
deps.dev confirmed. Three review cases carry a current-version RUSTSEC
vulnerability advisory, but not a malware label.

The purpose is calibration review, not an accusation against the maintainers.

| Package | Score | Downloads/wk | OSV | Main high-band driver | Review status |
|---|---:|---:|---|---|---|
| `@cloudbase/wx-cloud-client-sdk` | 56.9 | 35,669 | none | repeated publisher changes; no repository URL | likely first-party SDK; no advisory |
| `pgpass` | 53.5 | 96,781,575 | none | publisher email change; active repo; Scorecard available | likely legitimate email change; no advisory |
| `caniuse-api` | 50.5 | 20,465,944 | none | publisher/email change, long release dormancy, signing gap | likely legitimate transfer to MoOx; no advisory |
| `@apideck/better-ajv-errors` | 50.2 | 11,755,284 | none | publisher change; Scorecard available | likely legitimate first-party transfer; no advisory |
| `p-shells` | 53.7 | 13 | none | signing gap, commit anomaly, continuity | likely low-impact false-positive candidate; no advisory |
| `libbz2-rs-sys` | 51.4 | 22,770,231 | none | dependency risk, continuity, commit anomaly | likely legitimate crate; active foundation repo, no advisory |
| `psycopg-c` | 52.1 | 396,074 | none | commit anomaly, continuity, typosquat | likely legitimate; active psycopg repo, no advisory |
| `paste` | 53.2 | 131,565,569 | RUSTSEC-2024-0436 | dependency risk, bus factor, release anomaly | vulnerability, not malware; review |
| `bincode` | 52.9 | 81,557,886 | RUSTSEC-2025-0141 | bus factor, dependency risk, release anomaly | vulnerability, not malware; review |
| `proc-macro-error` | 51.2 | 48,350,595 | RUSTSEC-2024-0370 | bus factor, release anomaly, vulnerability | vulnerability, not malware; review |

## What the evidence says

- Three review cases have current-version RUSTSEC vulnerability advisories; the other seven have none.
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
- `psycopg-c` has an active psycopg repository and no advisory; its typosquat
  and commit signals need careful review before calling it a package risk.
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
