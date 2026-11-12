# Incident validation (pre-incident replay)

For each historical incident we rebuild the package context using **only
versions published before the incident cutoff**, then compute the release-based
signals. `bus_factor` and `account_age` are excluded because the available
GitHub statistics are current-state and would leak future information;
`typosquat` is excluded because the top-package list is current. The replay
score therefore covers `publisher_change`, `release_anomaly` and `signing_gap`,
renormalised to 0-100 over the signals that are applicable (weights 30/15/10).

A high replay score means the package looked risky *before* the incident. It is
not proof of compromise, and a low score is a miss to be reported honestly.

## Incidents

| Incident | Package | Cutoff | publisher_change | release_anomaly | signing_gap | Replay score | Band | Applicable |
|---|---|---|---|---|---|---|---|---|
| event-stream | npm/event-stream | 2018-11-20 | 0.50 | 0.11 | 1.00 | 48.4 | medium | publisher_change, release_anomaly, signing_gap |
| ua-parser-js | npm/ua-parser-js | 2021-10-21 | 0.00 | 0.00 | – | 0.0 | low | publisher_change, release_anomaly |
| colors | npm/colors | 2022-01-07 | 0.00 | 0.80 | 1.00 | 40.0 | medium | publisher_change, release_anomaly, signing_gap |
| node-ipc | npm/node-ipc | 2022-03-14 | 0.00 | 0.72 | 1.00 | 38.0 | medium | publisher_change, release_anomaly, signing_gap |
| tukaani-project/xz | github/tukaani-project/xz | 2024-02-23 | – | 0.19 | – | 18.9 | low | release_anomaly |

## Metrics

Benign sample: 27 packages with no known compromise, cutoff 2024-01-01. The label is a proxy, not ground truth.

| Threshold | TP | FP | FN | TN | Precision | Recall | False-positive rate |
|---|---|---|---|---|---|---|---|
| 25 | 3 | 11 | 2 | 16 | 0.214 | 0.600 | 0.407 |
| 40 | 2 | 7 | 3 | 20 | 0.222 | 0.400 | 0.259 |
| 50 | 0 | 6 | 5 | 21 | 0.000 | 0.000 | 0.222 |

## Notes

- **event-stream** (2018-11-20): Malicious flatmap-stream dependency introduced through a new publisher. replay=48.4 (medium), signals=publisher_change, release_anomaly, signing_gap.
- **ua-parser-js** (2021-10-21): Maintainer account hijacked; malicious versions published. replay=0.0 (low), signals=publisher_change, release_anomaly.
- **colors** (2022-01-07): Maintainer intentionally broke releases (sabotage, not takeover). replay=40.0 (medium), signals=publisher_change, release_anomaly, signing_gap.
- **node-ipc** (2022-03-14): Protestware release. replay=38.0 (medium), signals=publisher_change, release_anomaly, signing_gap.
- **tukaani-project/xz** (2024-02-23): Maintainer/commit-level backdoor; release-only signals are expected to miss it. replay=18.9 (low), signals=release_anomaly.

## Limitations

- Publisher identity comes from npm `_npmUser` or GitHub release authors;
  older versions may lack it.
- Release anomalies need at least three dated releases before the cutoff.
- `ua-parser-js` is a known miss: the account was hijacked without a
  publisher change, so release metadata alone cannot see it.
- `xz-utils` is a known miss in the release-only replay: the backdoor was
  introduced through commit-level maintainer changes, not a release
  anomaly. This motivates the commit-level work in the roadmap.
- Maven release cadence is not assessed, so Maven packages only contribute
  where other replay signals apply.
- A full replay would require historical repository and download snapshots;
  this MVP replays release metadata only.
