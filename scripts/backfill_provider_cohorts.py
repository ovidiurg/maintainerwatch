#!/usr/bin/env python3
"""Backfill deps.dev findings/impact for selected score bands."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from mw import db
from mw.config import load_config
from mw.ingest import depsdev, findings, forge
from mw.ingest.github import parse_github_repo
from mw.ingest.scorecard import fetch_scorecard
from mw.pipeline import make_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bands", default="high,medium")
    parser.add_argument("--providers", default="depsdev")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    bands = [item.strip() for item in args.bands.split(",") if item.strip()]
    providers = {item.strip() for item in args.providers.split(",") if item.strip()}
    if providers - {"depsdev", "github"}:
        raise SystemExit("supported providers: depsdev, github")

    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    placeholders = ",".join("?" for _ in bands)
    if providers == {"github"}:
        rows = conn.execute(
            f"""SELECT s.system, s.name, s.band, p.repo_url,
                       r.name AS has_stats, r.scorecard_checks_json
                FROM scores s
                JOIN packages p ON p.system=s.system AND p.name=s.name
                LEFT JOIN repo_stats r
                  ON r.system=s.system AND r.name=s.name
                WHERE s.model_version=? AND s.band IN ({placeholders})
                  AND p.repo_url IS NOT NULL AND p.repo_url != ''
                  AND (r.name IS NULL OR r.scorecard_checks_json IS NULL)
                ORDER BY CASE s.band WHEN 'high' THEN 0 ELSE 1 END,
                         p.downloads_weekly DESC, p.name
                LIMIT ?""",
            [cfg.model_version, *bands, args.limit or -1],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT s.system, s.name, s.band,
                       (SELECT v.version FROM versions v
                        WHERE v.system=s.system AND v.name=s.name
                        ORDER BY COALESCE(v.published_at,'') DESC, v.version DESC
                        LIMIT 1) AS version,
                       f.name AS has_findings, i.name AS has_impact
                FROM scores s
                JOIN packages p ON p.system=s.system AND p.name=s.name
                LEFT JOIN package_findings f
                  ON f.system=s.system AND f.name=s.name
                LEFT JOIN package_impact i
                  ON i.system=s.system AND i.name=s.name
                WHERE s.model_version=? AND s.band IN ({placeholders})
                  AND (f.name IS NULL OR i.name IS NULL)
                ORDER BY CASE s.band WHEN 'high' THEN 0 ELSE 1 END,
                         p.downloads_weekly DESC, p.name
                LIMIT ?""",
            [cfg.model_version, *bands, args.limit or -1],
        ).fetchall()
    count = 0
    with make_client(cfg) as client:
        for row in rows:
            if "repo_url" in row.keys():
                if row["repo_url"] and parse_github_repo(row["repo_url"]):
                    if row["has_stats"] is None:
                        stats = forge.fetch_repo_stats(
                            client, row["system"], row["name"], row["repo_url"],
                            cfg.github_token, cfg.gitlab_token,
                        )
                        if stats is None:
                            continue
                        db.upsert_repo_stats(conn, [stats])
                        count += 1
                    if row["scorecard_checks_json"] is None:
                        score, checks = fetch_scorecard(client, row["repo_url"])
                        if score is not None or checks is not None:
                            db.update_repo_scorecard(conn, row["system"], row["name"], score, checks)
                            count += 1
                continue
            if not row["version"]:
                continue
            changed = False
            if row["has_findings"] is None:
                doc = findings.fetch_findings(
                    client, row["system"], row["name"], row["version"]
                )
                if doc is not None:
                    db.upsert_findings(conn, [(
                        row["system"], row["name"], row["version"],
                        json.dumps(doc, sort_keys=True),
                        datetime.now(timezone.utc).isoformat(),
                    )])
                    changed = True
            if row["has_impact"] is None:
                impact = depsdev.fetch_dependents(
                    client, row["system"], row["name"], row["version"]
                )
                if impact is not None:
                    db.upsert_impact(conn, [(
                        row["system"], row["name"], row["version"],
                        impact["dependent_count"], impact["direct_dependent_count"],
                        impact["indirect_dependent_count"], "deps.dev",
                        datetime.now(timezone.utc).isoformat(),
                    )])
                    changed = True
            if changed:
                count += 1
    conn.close()
    print(json.dumps({"requested": len(rows), "updated": count, "bands": bands}, indent=2))


if __name__ == "__main__":
    main()
