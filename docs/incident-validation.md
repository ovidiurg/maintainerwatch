# Incident validation (pre-incident replay)

For each historical incident we rebuild the package context using **only
versions published before the incident cutoff**, then compute the release-based
signals. `bus_factor` and `account_age` are excluded because the available
GitHub statistics are current-state and would leak future information;
`typosquat` is excluded because the top-package list is current. The replay
score therefore covers `publisher_change`, `release_anomaly`, `signing_gap` and
`commit_anomaly`, renormalised to 0-100 over the signals that are applicable
(weights 30/10/10/15).

A high replay score means the package looked risky *before* the incident. It is
not proof of compromise, and a low score is a miss to be reported honestly.

## Incidents

| Incident | Package | Cutoff | publisher_change | release_anomaly | signing_gap | commit_anomaly | Replay score | Band | Applicable |
|---|---|---|---|---|---|---|---|---|---|
| event-stream | npm/event-stream | 2018-11-20 | 0.50 | 0.09 | 1.00 | 1.00 | 62.9 | high | publisher_change, release_anomaly, signing_gap, commit_anomaly |
| ua-parser-js | npm/ua-parser-js | 2021-10-21 | 0.00 | 0.00 | – | 1.00 | 27.3 | medium | publisher_change, release_anomaly, commit_anomaly |
| colors | npm/colors | 2022-01-07 | 0.00 | 0.80 | 0.30 | – | 22.0 | low | publisher_change, release_anomaly, signing_gap |
| node-ipc | npm/node-ipc | 2022-03-14 | 0.00 | 0.69 | 0.30 | – | 19.7 | low | publisher_change, release_anomaly, signing_gap |
| eslint-scope | npm/eslint-scope | 2018-07-11 | 0.03 | 0.00 | 0.30 | 0.00 | 6.0 | low | publisher_change, release_anomaly, signing_gap, commit_anomaly |
| eslint-config-eslint | npm/eslint-config-eslint | 2018-07-11 | 0.00 | 0.21 | 0.50 | 0.00 | 11.0 | low | publisher_change, release_anomaly, signing_gap, commit_anomaly |
| coa | npm/coa | 2021-10-21 | 0.00 | 0.80 | 0.30 | – | 22.0 | low | publisher_change, release_anomaly, signing_gap |
| rc | npm/rc | 2021-11-14 | 0.00 | 0.00 | 0.30 | – | 6.0 | low | publisher_change, release_anomaly, signing_gap |
| tukaani-project/xz | github/tukaani-project/xz | 2024-02-23 | – | 0.12 | – | 0.67 | 44.8 | medium | release_anomaly, commit_anomaly |
| eslint-config-prettier | npm/eslint-config-prettier | 2025-07-17 | 0.50 | 0.70 | 0.60 | – | 56.0 | high | publisher_change, release_anomaly, signing_gap |
| eslint-plugin-prettier | npm/eslint-plugin-prettier | 2025-07-17 | 0.00 | 0.00 | 0.00 | – | 0.0 | low | publisher_change, release_anomaly, signing_gap |
| is | npm/is | 2025-07-17 | 0.00 | 0.80 | 0.30 | – | 22.0 | low | publisher_change, release_anomaly, signing_gap |
| got-fetch | npm/got-fetch | 2025-07-17 | 0.00 | 0.14 | – | – | 3.5 | low | publisher_change, release_anomaly |
| synckit | npm/synckit | 2025-07-17 | 0.00 | 0.70 | 0.40 | – | 22.0 | low | publisher_change, release_anomaly, signing_gap |
| @pkgr/core | npm/@pkgr/core | 2025-07-17 | 0.00 | 0.70 | 0.00 | – | 14.0 | low | publisher_change, release_anomaly, signing_gap |
| napi-postinstall | npm/napi-postinstall | 2025-07-17 | 0.00 | 0.23 | 0.00 | – | 17.2 | low | publisher_change, release_anomaly, signing_gap, package_age |
| reviewdog/action-setup | github/reviewdog/action-setup | 2025-03-10 | – | 0.00 | – | – | 0.0 | low | release_anomaly |
| keyv | npm/keyv | 2026-08-03 | 0.00 | 0.00 | 0.60 | – | 12.0 | low | publisher_change, release_anomaly, signing_gap |
| file-entry-cache | npm/file-entry-cache | 2026-08-03 | 0.00 | 0.09 | 0.80 | – | 17.8 | low | publisher_change, release_anomaly, signing_gap |

## Metrics

Benign sample: 46 packages with no known compromise, cutoff 2024-01-01. The label is a proxy, not ground truth.

| Threshold | TP | FP | FN | TN | Precision | Recall | False-positive rate |
|---|---|---|---|---|---|---|---|
| 25 | 4 | 10 | 15 | 36 | 0.286 | 0.211 | 0.217 |
| 40 | 3 | 8 | 16 | 38 | 0.273 | 0.158 | 0.174 |
| 50 | 2 | 6 | 17 | 40 | 0.250 | 0.105 | 0.130 |

## Maintainer-continuity sensitivity

The baseline replay above excludes `maintainer_continuity`. A diagnostic
sensitivity run on the same 19 incidents and 46 benign packages, adding
that signal, gives:

| Weight | TP | FP | Precision | Recall | FPR |
|---|---|---|---|---|---|
| 10 | 3 | 8 | 0.273 | 0.158 | 0.174 |
| 15 | 4 | 8 | 0.333 | 0.211 | 0.174 |

At weight 15, `ua-parser-js` reaches 40.7 and `event-stream` reaches
68.0; no additional benign package crosses 40. The sample is too small
to treat this as a production threshold.

## Notes

- **event-stream** (2018-11-20): Malicious flatmap-stream dependency introduced through a new publisher. replay=62.9 (high), signals=publisher_change, release_anomaly, signing_gap, commit_anomaly.
- **ua-parser-js** (2021-10-21): Maintainer account hijacked; malicious versions published. replay=27.3 (medium), signals=publisher_change, release_anomaly, commit_anomaly.
- **colors** (2022-01-07): Maintainer intentionally broke releases (sabotage, not takeover). replay=22.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **node-ipc** (2022-03-14): Protestware release. replay=19.7 (low), signals=publisher_change, release_anomaly, signing_gap.
- **eslint-scope** (2018-07-11): Compromised eslint publisher account; malicious release used the same account. replay=6.0 (low), signals=publisher_change, release_anomaly, signing_gap, commit_anomaly.
- **eslint-config-eslint** (2018-07-11): Same compromised eslint account; companion malicious package. replay=11.0 (low), signals=publisher_change, release_anomaly, signing_gap, commit_anomaly.
- **coa** (2021-10-21): Compromised maintainer account; malicious coa releases. replay=22.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **rc** (2021-11-14): Compromised maintainer account; malicious rc releases. replay=6.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **tukaani-project/xz** (2024-02-23): Maintainer/commit-level backdoor; release-only signals are expected to miss it. replay=44.8 (medium), signals=release_anomaly, commit_anomaly.
- **eslint-config-prettier** (2025-07-17): npnjs.com phishing campaign; malicious releases published through a compromised maintainer. replay=56.0 (high), signals=publisher_change, release_anomaly, signing_gap.
- **eslint-plugin-prettier** (2025-07-17): Same npnjs.com campaign; companion package with malicious releases. replay=0.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **is** (2025-07-17): Maintainer phishing campaign; Scavenger malware shipped through the is package. replay=22.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **got-fetch** (2025-07-17): Maintainer phishing campaign; Pycoon stealer in rogue releases. replay=3.5 (low), signals=publisher_change, release_anomaly.
- **synckit** (2025-07-17): Maintainer phishing campaign; malicious release without a matching source change. replay=22.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **@pkgr/core** (2025-07-17): Maintainer phishing campaign; Scavenger payload in a rogue release. replay=14.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **napi-postinstall** (2025-07-17): Maintainer phishing campaign; install path executed attacker-controlled code. replay=17.2 (low), signals=publisher_change, release_anomaly, signing_gap, package_age.
- **reviewdog/action-setup** (2025-03-10): Compromised contributor token used to publish malicious GitHub Action releases. replay=0.0 (low), signals=release_anomaly.
- **keyv** (2026-08-03): jaredwray account takeover; ChainDrop preinstall credential harvester. replay=12.0 (low), signals=publisher_change, release_anomaly, signing_gap.
- **file-entry-cache** (2026-08-03): Same ChainDrop worm campaign in the jaredwray package family. replay=17.8 (low), signals=publisher_change, release_anomaly, signing_gap.

## Limitations

- Publisher identity comes from npm `_npmUser` or GitHub release authors;
  older versions may lack it.
- Release anomalies need at least three dated releases before the cutoff.
- Commit-level signals need `mw backfill-commits`; historical incidents must
  be fetched with `--until`. Without commits, `commit_anomaly` shows `–`.
- Same-account hijacks can stay low: release-only replay leaves
  `ua-parser-js` at 27.3 and `eslint-scope`, `eslint-config-eslint`,
  `coa` and `rc` low because publisher identity did not change. A
  sensitivity run that adds `maintainer_continuity` raises ua-parser-js
  to 40.7, but the sample is small.
- `xz-utils` is a hard case: the backdoor came through a long-term
  maintainer, so new-author and burst signals may not fire before the cutoff.
- Maven release cadence is not assessed, so Maven packages only contribute
  where other replay signals apply.
- A full replay would require historical repository and download snapshots;
  this MVP replays release metadata plus the commits fetched per package.
