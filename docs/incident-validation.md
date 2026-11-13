# Incident validation (pre-incident replay)

For each historical incident we rebuild the package context using **only
versions published before the incident cutoff**, then compute the release-based
signals. `bus_factor` and `account_age` are excluded because the available
GitHub statistics are current-state and would leak future information;
`typosquat` is excluded because the top-package list is current. The replay
score therefore covers `publisher_change`, `release_anomaly`, `signing_gap` and
`commit_anomaly`, renormalised to 0-100 over the signals that are applicable
(weights 30/15/10/20).

A high replay score means the package looked risky *before* the incident. It is
not proof of compromise, and a low score is a miss to be reported honestly.

## Incidents

| Incident | Package | Cutoff | publisher_change | release_anomaly | signing_gap | commit_anomaly | Replay score | Band | Applicable |
|---|---|---|---|---|---|---|---|---|---|
| event-stream | npm/event-stream | 2018-11-20 | 0.50 | 0.11 | 1.00 | 1.00 | 59.5 | high | publisher_change, release_anomaly, signing_gap, commit_anomaly |
| ua-parser-js | npm/ua-parser-js | 2021-10-21 | 0.00 | 0.00 | – | 1.00 | 25.0 | medium | publisher_change, release_anomaly, commit_anomaly |
| colors | npm/colors | 2022-01-07 | 0.00 | 0.80 | 0.30 | – | 27.3 | medium | publisher_change, release_anomaly, signing_gap |
| node-ipc | npm/node-ipc | 2022-03-14 | 0.00 | 0.72 | 0.30 | – | 25.2 | medium | publisher_change, release_anomaly, signing_gap |
| tukaani-project/xz | github/tukaani-project/xz | 2024-02-23 | – | 0.19 | – | 0.67 | 42.8 | medium | release_anomaly, commit_anomaly |

## Metrics

Benign sample: 27 packages with no known compromise, cutoff 2024-01-01. The label is a proxy, not ground truth.

| Threshold | TP | FP | FN | TN | Precision | Recall | False-positive rate |
|---|---|---|---|---|---|---|---|
| 25 | 5 | 9 | 0 | 18 | 0.357 | 1.000 | 0.333 |
| 40 | 2 | 4 | 3 | 23 | 0.333 | 0.400 | 0.148 |
| 50 | 1 | 4 | 4 | 23 | 0.200 | 0.200 | 0.148 |

## Notes

- **event-stream** (2018-11-20): Malicious flatmap-stream dependency introduced through a new publisher. replay=59.5 (high), signals=publisher_change, release_anomaly, signing_gap, commit_anomaly.
- **ua-parser-js** (2021-10-21): Maintainer account hijacked; malicious versions published. replay=25.0 (medium), signals=publisher_change, release_anomaly, commit_anomaly.
- **colors** (2022-01-07): Maintainer intentionally broke releases (sabotage, not takeover). replay=27.3 (medium), signals=publisher_change, release_anomaly, signing_gap.
- **node-ipc** (2022-03-14): Protestware release. replay=25.2 (medium), signals=publisher_change, release_anomaly, signing_gap.
- **tukaani-project/xz** (2024-02-23): Maintainer/commit-level backdoor; release-only signals are expected to miss it. replay=42.8 (medium), signals=release_anomaly, commit_anomaly.

## Limitations

- Publisher identity comes from npm `_npmUser` or GitHub release authors;
  older versions may lack it.
- Release anomalies need at least three dated releases before the cutoff.
- Commit-level signals need `mw backfill-commits`; historical incidents must
  be fetched with `--until`. Without commits, `commit_anomaly` shows `–`.
- `ua-parser-js` can still be missed: the account was hijacked without a
  publisher change, and commit-level signals only see the same author.
- `xz-utils` is a hard case: the backdoor came through a long-term
  maintainer, so new-author and burst signals may not fire before the cutoff.
- Maven release cadence is not assessed, so Maven packages only contribute
  where other replay signals apply.
- A full replay would require historical repository and download snapshots;
  this MVP replays release metadata plus the commits fetched per package.
