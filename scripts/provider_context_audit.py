#!/usr/bin/env python3
"""Audit provider consensus for the current high-band packages."""

from __future__ import annotations

import json
from pathlib import Path

from mw import db, providers
from mw.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = conn.execute(
        """SELECT s.system, s.name, s.score, s.band, p.downloads_weekly
           FROM scores s
           JOIN packages p ON p.system=s.system AND p.name=s.name
           WHERE s.model_version=? AND s.band='high'
           ORDER BY s.score DESC, s.name""",
        (cfg.model_version,),
    ).fetchall()
    records = []
    for row in rows:
        context = providers.build_context(conn, row["system"], row["name"])
        if context is None:
            continue
        consensus = context["consensus"]
        if consensus["advisory"] == "confirmed":
            status = "confirmed"
        elif consensus["conflicts"]:
            status = "conflict"
        elif consensus["advisory"] == "unknown":
            status = "unknown"
        else:
            status = "unconfirmed"
        records.append({
            "system": row["system"],
            "name": row["name"],
            "score": row["score"],
            "downloads_weekly": row["downloads_weekly"],
            "status": status,
            "advisory": consensus["advisory"],
            "coverage": consensus["coverage"],
            "osv": context["osv"]["status"],
            "depsdev": context["depsdev"]["status"],
            "scorecard": context["scorecard"]["status"],
            "conflicts": consensus["conflicts"],
        })
    conn.close()
    counts = {
        status: sum(1 for item in records if item["status"] == status)
        for status in ("confirmed", "conflict", "unknown", "unconfirmed")
    }
    payload = {"model_version": cfg.model_version, "counts": counts, "packages": records}
    out_json = ROOT / "data" / "validation" / "provider-context-audit.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Provider context audit",
        "",
        f"Model: `{cfg.model_version}`",
        "",
        "| Package | Score | Downloads/wk | Status | OSV | deps.dev | Scorecard | Coverage |",
        "|---|---:|---:|---|---|---|---|---:|",
    ]
    for item in records:
        lines.append(
            f"| `{item['name']}` | {item['score']} | {item['downloads_weekly'] or 0} | "
            f"{item['status']} | {item['osv']} | {item['depsdev']} | "
            f"{item['scorecard']} | {item['coverage']:.0%} |"
        )
    lines.extend([
        "",
        "## Counts",
        "",
        f"- confirmed: **{counts['confirmed']}**",
        f"- conflict: **{counts['conflict']}**",
        f"- unknown: **{counts['unknown']}**",
        f"- unconfirmed: **{counts['unconfirmed']}**",
        "",
        "This is a read-only triage report. It does not change scores or bands.",
    ])
    out_md = ROOT / "docs" / "validation" / "provider-context-audit.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "packages": len(records), "out": str(out_md)}, indent=2))


if __name__ == "__main__":
    main()
