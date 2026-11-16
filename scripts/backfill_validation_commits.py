#!/usr/bin/env python3
"""Backfill commit history before each validation cutoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mw import db, validation
from mw.config import load_config
from mw.ingest import forge
from mw.pipeline import make_client

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="validation/v1")
    parser.add_argument("--config", default="config/validation-replay.yaml")
    parser.add_argument("--positives-only", action="store_true")
    args = parser.parse_args()
    positives_only = args.positives_only
    cfg = load_config(args.config)
    incidents, packages, controls = validation.load_dataset(ROOT / args.dataset)
    incident_by_id = {item["incident_id"]: item for item in incidents}

    cutoffs: dict[tuple[str, str], str] = {}
    for item in packages:
        if item.get("system") not in {"npm", "pypi"} or not item.get("package"):
            continue
        incident = incident_by_id.get(item.get("incident_id"), {})
        cutoff = incident.get("observation_cutoff") or (
            f"{incident.get('disclosure_date', '')}T00:00:00Z"
        )
        key = (item["system"], item["package"])
        if key not in cutoffs or cutoff < cutoffs[key]:
            cutoffs[key] = cutoff
    if not positives_only:
        for item in controls:
            if item.get("system") in {"npm", "pypi"}:
                cutoffs[(item["system"], item["package"])] = (
                    item.get("as_of") or "2026-01-01T00:00:00Z"
                )

    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = {
        (row["system"], row["name"]): row
        for row in db.list_packages(conn)
    }
    total_commits = 0
    fetched = 0
    with make_client(cfg) as client:
        for (system, name), cutoff in sorted(cutoffs.items()):
            row = rows.get((system, name))
            if row is None or not row["repo_url"]:
                continue
            commits = forge.fetch_commits(
                client, row["repo_url"], cfg.github_token, cfg.gitlab_token,
                until=cutoff, pages=2,
            )
            if not commits:
                continue
            db.upsert_commits(
                conn,
                [
                    (system, name, c["sha"], c["committed_at"],
                     c["author_login"], c["author_email"])
                    for c in commits
                ],
            )
            conn.commit()
            fetched += 1
            total_commits += len(commits)
            if fetched % 20 == 0:
                print(f"fetched {fetched} repos, {total_commits} commits", flush=True)
    conn.close()
    print(json.dumps({"repos": fetched, "commits": total_commits}))


if __name__ == "__main__":
    main()
