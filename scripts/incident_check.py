from __future__ import annotations

from pathlib import Path

from mw import db
from mw.config import load_config
from mw.resolve import identity_map
from mw.score import band_for, compute_score
from mw.signals import compute_all
from mw.signals.base import Context

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
]

# Only signals derived from releases published before the cutoff are time-aware.
REPLAY_SIGNALS = ["publisher_change", "release_anomaly", "signing_gap"]

HEADER = """# Incident validation (pre-incident replay)

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
"""


def main() -> None:
    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    lines = [HEADER]
    notes: list[str] = []

    for system, name, cutoff, description in INCIDENTS:
        pkg = db.get_package(conn, system, name)
        if not pkg:
            lines.append(f"| {name} | {system}/{name} | {cutoff[:10]} | – | – | – | – | not ingested |\n")
            continue
        ctx = Context(
            conn=conn,
            system=system,
            name=name,
            downloads_weekly=int(pkg["downloads_weekly"] or 0),
            top_names=db.top_names(conn, system, 5000),
            identity_mapping=identity_map(conn, system, name, cfg.min_identity_confidence),
            as_of=cutoff,
        )
        signals = compute_all(ctx)
        weights = {k: cfg.weights[k] for k in REPLAY_SIGNALS}
        span = sum(weights.values())
        score = round(
            100.0 * sum(weights[k] * signals[k].value for k in REPLAY_SIGNALS) / span,
            1,
        )
        band = band_for(score)
        lines.append(
            f"| {name} | {system}/{name} | {cutoff[:10]} | "
            f"{signals['publisher_change'].value:.2f} | "
            f"{signals['release_anomaly'].value:.2f} | "
            f"{signals['signing_gap'].value:.2f} | "
            f"{score} | {band} |\n"
        )
        notes.append(
            f"- **{name}** ({cutoff[:10]}): {description} "
            f"publisher_change={signals['publisher_change'].value:.2f}, "
            f"release_anomaly={signals['release_anomaly'].value:.2f}, "
            f"signing_gap={signals['signing_gap'].value:.2f}."
        )

    lines.append("\n## Notes\n\n")
    lines.extend(n + "\n" for n in notes)
    lines.append(
        "\n## Limitations\n\n"
        "- Publisher identity comes from npm `_npmUser`; older versions may lack it.\n"
        "- Release anomalies need at least three dated releases before the cutoff.\n"
        "- A full replay would require historical repository and download snapshots;\n"
        "  this MVP replays release metadata only.\n"
    )

    out = Path("docs/incident-validation.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(lines), encoding="utf-8")
    print("".join(lines))


if __name__ == "__main__":
    main()
