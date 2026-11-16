#!/usr/bin/env python3
"""Backfill repository stats and recent commits for packages hosted on GitLab."""

from __future__ import annotations

import argparse

from mw import db
from mw.config import load_config
from mw.ingest import forge
from mw.pipeline import make_client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--commits", action="store_true")
    parser.add_argument("--pages", type=int, default=2)
    args = parser.parse_args()

    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = [
        row for row in conn.execute(
            """SELECT p.system, p.name, p.repo_url
               FROM packages p
               LEFT JOIN repo_stats r
                 ON r.system = p.system AND r.name = p.name
               WHERE p.repo_url LIKE '%gitlab.com%' AND r.name IS NULL
               ORDER BY p.system, p.name"""
        )
        if row["repo_url"]
    ]
    if args.limit:
        rows = rows[: args.limit]

    repos = 0
    commits = 0
    with make_client(cfg) as client:
        for row in rows:
            stats = forge.fetch_repo_stats(
                client, row["system"], row["name"], row["repo_url"],
                cfg.github_token, cfg.gitlab_token,
            )
            if stats is not None:
                db.upsert_repo_stats(conn, [stats])
                repos += 1
            if args.commits:
                package_commits = forge.fetch_commits(
                    client, row["repo_url"], cfg.github_token, cfg.gitlab_token,
                    pages=args.pages,
                )
                if package_commits:
                    db.upsert_commits(
                        conn,
                        [
                            (
                                row["system"], row["name"], c["sha"],
                                c["committed_at"], c.get("author_login"),
                                c.get("author_email"),
                            )
                            for c in package_commits
                        ],
                    )
                    commits += len(package_commits)
    conn.close()
    print({
        "packages": len(rows),
        "repo_stats": repos,
        "commits": commits,
    })


if __name__ == "__main__":
    main()
