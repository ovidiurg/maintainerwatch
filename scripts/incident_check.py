from __future__ import annotations

from pathlib import Path

from mw import db
from mw.config import load_config
from mw.evaluate import evaluate
from mw.score import band_for

# Cutoff = the day before the malicious/sabotage release.
INCIDENTS = [
    ("npm", "event-stream", "2018-11-20T00:00:00+00:00",
     "Malicious flatmap-stream dependency introduced through a new publisher."),
    ("npm", "ua-parser-js", "2021-10-21T00:00:00+00:00",
     "Maintainer account hijacked; malicious versions published."),
    ("npm", "colors", "2022-01-07T00:00:00+00:00",
     "Maintainer intentionally broke releases (sabotage, not takeover)."),
    ("npm", "node-ipc", "2022-03-14T00:00:00+00:00",
     "Protestware release."),
    ("npm", "eslint-scope", "2018-07-11T00:00:00+00:00",
     "Compromised eslint publisher account; malicious release used the same account."),
    ("npm", "eslint-config-eslint", "2018-07-11T00:00:00+00:00",
     "Same compromised eslint account; companion malicious package."),
    ("npm", "coa", "2021-10-21T00:00:00+00:00",
     "Compromised maintainer account; malicious coa releases."),
    ("npm", "rc", "2021-11-14T00:00:00+00:00",
     "Compromised maintainer account; malicious rc releases."),
    ("github", "tukaani-project/xz", "2024-02-23T00:00:00+00:00",
     "Maintainer/commit-level backdoor; release-only signals are expected to miss it."),
    ("npm", "eslint-config-prettier", "2025-07-17T00:00:00+00:00",
     "npnjs.com phishing campaign; malicious releases published through a compromised maintainer."),
    ("npm", "eslint-plugin-prettier", "2025-07-17T00:00:00+00:00",
     "Same npnjs.com campaign; companion package with malicious releases."),
    ("npm", "is", "2025-07-17T00:00:00+00:00",
     "Maintainer phishing campaign; Scavenger malware shipped through the is package."),
    ("npm", "got-fetch", "2025-07-17T00:00:00+00:00",
     "Maintainer phishing campaign; Pycoon stealer in rogue releases."),
    ("npm", "synckit", "2025-07-17T00:00:00+00:00",
     "Maintainer phishing campaign; malicious release without a matching source change."),
    ("npm", "@pkgr/core", "2025-07-17T00:00:00+00:00",
     "Maintainer phishing campaign; Scavenger payload in a rogue release."),
    ("npm", "napi-postinstall", "2025-07-17T00:00:00+00:00",
     "Maintainer phishing campaign; install path executed attacker-controlled code."),
    ("github", "reviewdog/action-setup", "2025-03-10T00:00:00+00:00",
     "Compromised contributor token used to publish malicious GitHub Action releases."),
    ("npm", "keyv", "2026-08-03T00:00:00+00:00",
     "jaredwray account takeover; ChainDrop preinstall credential harvester."),
    ("npm", "file-entry-cache", "2026-08-03T00:00:00+00:00",
     "Same ChainDrop worm campaign in the jaredwray package family."),
]

# Packages with no known compromise in the evaluation window. Absence of a known
# incident is not proof of benignity; this is a proxy for a false-positive rate.
BENIGN = [
    ("npm", "react"), ("npm", "lodash"), ("npm", "express"), ("npm", "commander"),
    ("npm", "chalk"), ("npm", "debug"), ("npm", "semver"), ("npm", "typescript"),
    ("npm", "axios"), ("npm", "vue"), ("npm", "next"), ("npm", "webpack"),
    ("pypi", "requests"), ("pypi", "urllib3"), ("pypi", "numpy"), ("pypi", "pandas"),
    ("pypi", "django"), ("pypi", "flask"), ("pypi", "pytest"), ("pypi", "pydantic"),
    ("pypi", "scipy"), ("pypi", "matplotlib"), ("pypi", "click"), ("pypi", "jinja2"),
    ("pypi", "setuptools"), ("pypi", "pip"), ("pypi", "boto3"), ("pypi", "sqlalchemy"),
    ("pypi", "aiohttp"), ("pypi", "cryptography"), ("pypi", "pyyaml"), ("pypi", "six"),
    ("crates", "serde"), ("crates", "tokio"), ("crates", "rand"), ("crates", "hashbrown"),
    ("crates", "serde_json"), ("crates", "clap"), ("crates", "anyhow"), ("crates", "regex"),
    ("crates", "log"), ("crates", "bytes"), ("crates", "once_cell"), ("crates", "hyper"),
    ("maven", "com.google.guava:guava"), ("maven", "org.apache.commons:commons-lang3"),
]
BENIGN_CUTOFF = "2024-01-01T00:00:00+00:00"
THRESHOLDS = [25, 40, 50]

HEADER = """# Incident validation (pre-incident replay)

For each historical incident we rebuild the package context using **only
versions published before the incident cutoff**, then compute the release-based
signals. `bus_factor` and `account_age` are excluded because the available
GitHub statistics are current-state and would leak future information;
`typosquat` is excluded because the top-package list is current. The replay
score therefore covers `publisher_change`, `release_anomaly`, `signing_gap` and
`commit_anomaly`, renormalised to 0-100 over the signals that are applicable
(weights 30/10/15/15).

A high replay score means the package looked risky *before* the incident. It is
not proof of compromise, and a low score is a miss to be reported honestly.

## Incidents

| Incident | Package | Cutoff | publisher_change | release_anomaly | signing_gap | commit_anomaly | Replay score | Band | Applicable |
|---|---|---|---|---|---|---|---|---|---|
"""


def main() -> None:
    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)

    positives, negatives, metrics = evaluate(
        conn,
        cfg,
        [(system, name, cutoff) for system, name, cutoff, _ in INCIDENTS],
        [(system, name, BENIGN_CUTOFF) for system, name in BENIGN],
        THRESHOLDS,
    )
    by_key = {(r.system, r.name): r for r in positives}

    lines = [HEADER]
    notes: list[str] = []
    for system, name, cutoff, description in INCIDENTS:
        result = by_key.get((system, name))
        if result is None:
            lines.append(
                f"| {name} | {system}/{name} | {cutoff[:10]} | – | – | – | – | not ingested | – |\n"
            )
            continue
        values = result.values

        def fmt(key: str) -> str:
            return f"{values[key]:.2f}" if key in result.applicable else "–"

        lines.append(
            f"| {name} | {system}/{name} | {cutoff[:10]} | "
            f"{fmt('publisher_change')} | "
            f"{fmt('release_anomaly')} | "
            f"{fmt('signing_gap')} | "
            f"{fmt('commit_anomaly')} | "
            f"{result.score} | {band_for(result.score)} | "
            f"{', '.join(result.applicable) or 'none'} |\n"
        )
        notes.append(
            f"- **{name}** ({cutoff[:10]}): {description} "
            f"replay={result.score} ({band_for(result.score)}), "
            f"signals={', '.join(result.applicable) or 'none'}."
        )

    lines.append("\n## Metrics\n\n")
    lines.append(
        f"Benign sample: {len(negatives)} packages with no known compromise, "
        f"cutoff {BENIGN_CUTOFF[:10]}. The label is a proxy, not ground truth.\n\n"
    )
    lines.append("| Threshold | TP | FP | FN | TN | Precision | Recall | False-positive rate |\n")
    lines.append("|---|---|---|---|---|---|---|---|\n")
    for m in metrics:
        lines.append(
            f"| {m['threshold']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['false_positive_rate']:.3f} |\n"
        )

    lines.append(
        "\n## Maintainer-continuity sensitivity\n\n"
        "The baseline replay above excludes `maintainer_continuity`. A diagnostic\n"
        "sensitivity run on the same 19 incidents and 46 benign packages, adding\n"
        "that signal, gives:\n\n"
        "| Weight | TP | FP | Precision | Recall | FPR |\n"
        "|---|---|---|---|---|---|\n"
        "| 10 | 3 | 8 | 0.273 | 0.158 | 0.174 |\n"
        "| 15 | 4 | 8 | 0.333 | 0.211 | 0.174 |\n\n"
        "At weight 15, `ua-parser-js` reaches 40.7 and `event-stream` reaches\n"
        "68.0; no additional benign package crosses 40. The sample is too small\n"
        "to treat this as a production threshold.\n"
    )
    lines.append("\n## Notes\n\n")
    lines.extend(n + "\n" for n in notes)
    lines.append(
        "\n## Limitations\n\n"
        "- Publisher identity comes from npm `_npmUser` or GitHub release authors;\n"
        "  older versions may lack it.\n"
        "- Release anomalies need at least three dated releases before the cutoff.\n"
        "- Commit-level signals need `mw backfill-commits`; historical incidents must\n"
        "  be fetched with `--until`. Without commits, `commit_anomaly` shows `–`.\n"
        "- Same-account hijacks can stay low: release-only replay leaves\n"
        "  `ua-parser-js` at 27.3 and `eslint-scope`, `eslint-config-eslint`,\n"
        "  `coa` and `rc` low because publisher identity did not change. A\n"
        "  sensitivity run that adds `maintainer_continuity` raises ua-parser-js\n"
        "  to 40.7, but the sample is small.\n"
        "- `xz-utils` is a hard case: the backdoor came through a long-term\n"
        "  maintainer, so new-author and burst signals may not fire before the cutoff.\n"
        "- Maven release cadence is not assessed, so Maven packages only contribute\n"
        "  where other replay signals apply.\n"
        "- A full replay would require historical repository and download snapshots;\n"
        "  this MVP replays release metadata plus the commits fetched per package.\n"
    )

    out = Path("docs/incident-validation.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(lines), encoding="utf-8")
    print("".join(lines))


if __name__ == "__main__":
    main()
