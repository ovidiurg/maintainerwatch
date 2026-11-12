# Incident validation (pre-incident replay)

For each historical incident we rebuild the package context using **only
versions published before the incident cutoff**, then compute the release-based
signals. `bus_factor` and `account_age` are excluded because the available
GitHub statistics are current-state and would leak future information;
`typosquat` is excluded because the top-package list is current. The replay
score therefore covers `publisher_change`, `release_anomaly` and `signing_gap`,
renormalised to 0-100 (weights 30/15/10).

A high replay score means the package looked risky *before* the incident. It is
not proof of compromise, and a low score is a miss to be reported honestly.

| Incident | Package | Cutoff | publisher_change | release_anomaly | signing_gap | Replay score | Band |
|---|---|---|---|---|---|---|---|
| event-stream | npm/event-stream | 2018-11-20 | 0.50 | 0.11 | 1.00 | 48.4 | medium |
| ua-parser-js | npm/ua-parser-js | 2021-10-21 | 0.00 | 0.00 | 0.00 | 0.0 | low |
| colors | npm/colors | 2022-01-07 | 0.00 | 0.80 | 1.00 | 40.0 | medium |
| node-ipc | npm/node-ipc | 2022-03-14 | 0.00 | 0.72 | 1.00 | 38.0 | medium |

## Notes

- **event-stream** (2018-11-20): Malicious flatmap-stream dependency introduced through a new publisher. publisher_change=0.50, release_anomaly=0.11, signing_gap=1.00.
- **ua-parser-js** (2021-10-21): Maintainer account hijacked; malicious versions published. publisher_change=0.00, release_anomaly=0.00, signing_gap=0.00.
- **colors** (2022-01-07): Maintainer intentionally broke releases (sabotage, not takeover). publisher_change=0.00, release_anomaly=0.80, signing_gap=1.00.
- **node-ipc** (2022-03-14): Protestware release. publisher_change=0.00, release_anomaly=0.72, signing_gap=1.00.

## Limitations

- Publisher identity comes from npm `_npmUser`; older versions may lack it.
- Release anomalies need at least three dated releases before the cutoff.
- A full replay would require historical repository and download snapshots;
  this MVP replays release metadata only.
