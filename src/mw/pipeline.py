from __future__ import annotations

import hashlib
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import httpx

from . import db, snapshots
from .config import Config
from .impact import impact_score, impact_tier
from .export import export_dataset
from .ingest import crates, depsdev, downloads, findings, forge, github, github_repo, maven, npm, osv, pypi
from .ingest.http import CachedClient
from .ingest.scorecard import fetch_scorecard
from .models import Maintainer, Version
from .report import build_report
from .resolve import identity_map, resolve_package
from .risk import describe_risk
from .score import band_for, compute_score, computed_at
from .signals import SIGNALS, compute_all
from .signals.base import Context, parse_ts
from .signals.typosquat import TARGET_MIN_DOWNLOADS


def make_client(cfg: Config) -> CachedClient:
    return CachedClient(
        cache_dir=cfg.data_dir / "cache",
        timeout_s=cfg.http.timeout_s,
        ttl_h=cfg.http.cache_ttl_h,
        rate_limit_qps=cfg.http.rate_limit_qps,
        user_agent=cfg.http.user_agent,
    )


def _open(cfg: Config):
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    return conn


def ingest_system(
    cfg: Config,
    system: str,
    top_n: int | None = None,
    seed_file: str | None = None,
    with_github: bool = True,
) -> dict:
    conn = _open(cfg)
    top_n = top_n or cfg.top_n

    modules = {
        "npm": npm,
        "pypi": pypi,
        "crates": crates,
        "maven": maven,
        "github": github_repo,
    }
    module = modules.get(system)
    if module is None:
        raise ValueError(f"unsupported system: {system}")
    fetch_top = module.fetch_top
    fetch_package = module.fetch_package
    fetch_dependencies = module.fetch_dependencies

    packages = []
    versions: list[Version] = []
    maintainers: list[Maintainer] = []
    captured_at = datetime.now(timezone.utc).isoformat()

    with make_client(cfg) as client:
        names = fetch_top(client, top_n, seed_file)

        for name in names:
            if system == "github":
                result = fetch_package(client, name, token=cfg.github_token)
            else:
                result = fetch_package(client, name)
            if not result:
                continue
            pkg, pkg_versions, pkg_maintainers = result
            if system in ("npm", "pypi"):
                pkg.downloads_weekly = downloads.fetch_downloads(client, system, name)

            dep_names = fetch_dependencies(client, name)
            latest = max(
                pkg_versions, key=lambda v: v.published_at or "", default=None
            )
            dep_rows = [
                (system, name, latest.version if latest else "", system, dep)
                for dep in dep_names
            ]
            db.clear_package_dependencies(conn, system, name)
            if dep_rows:
                db.upsert_dependencies(conn, dep_rows)

            packages.append(pkg)
            versions.extend(pkg_versions)
            maintainers.extend(pkg_maintainers)

            db.upsert_packages(conn, [pkg])
            db.upsert_versions(conn, pkg_versions)
            db.upsert_maintainers(conn, pkg_maintainers)

            identity_set = sorted({m.identity for m in pkg_maintainers})
            payload = json.dumps(identity_set, sort_keys=True)
            db.record_snapshot(
                conn, system, name, captured_at, payload,
                hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            )

        db.update_dependency_counts(conn)
        conn.commit()

        vulns = osv.fetch_vulns(client, [(system, n) for n in names])
        osv_rows = []
        counts: dict[tuple[str, str], int] = {}
        for (s, n), entries in vulns.items():
            counts[(s, n)] = len(entries)
            for vuln_id, severity, published in entries:
                osv_rows.append((s, n, vuln_id, severity, published, None, None, None))
        db.upsert_osv(conn, osv_rows)
        db.update_osv_counts(conn, counts)
        conn.commit()

        github_count = 0
        if with_github:
            for pkg in packages:
                if not pkg.repo_url:
                    continue
                stats = forge.fetch_repo_stats(
                    client, system, pkg.name, pkg.repo_url,
                    cfg.github_token, cfg.gitlab_token,
                )
                if not stats:
                    continue
                if github.parse_github_repo(pkg.repo_url):
                    stats.scorecard_score, stats.scorecard_checks_json = fetch_scorecard(
                        client, pkg.repo_url
                    )
                db.upsert_repo_stats(conn, [stats])
                github_count += 1
            conn.commit()

    conn.close()
    return {
        "system": system,
        "packages": len(packages),
        "versions": len(versions),
        "maintainers": len(maintainers),
        "vuln_packages": sum(1 for c in counts.values() if c),
        "github_repos": github_count,
    }


def _version_models(rows) -> list[Version]:
    return [
        Version(
            system=r["system"],
            name=r["name"],
            version=r["version"],
            published_at=r["published_at"],
            publisher_name=r["publisher_name"],
            publisher_email=r["publisher_email"],
            has_sig=bool(r["has_sig"]),
            has_provenance=bool(r["has_provenance"]),
            is_yanked=bool(r["is_yanked"]),
        )
        for r in rows
    ]


def _maintainer_models(rows) -> list[Maintainer]:
    return [
        Maintainer(
            system=r["system"],
            name=r["name"],
            identity=r["identity"],
            role=r["role"] or "maintainer",
            source=r["source"] or "registry",
            account_created_at=r["account_created_at"],
            first_seen=r["first_seen"],
            last_seen=r["last_seen"],
        )
        for r in rows
    ]


def backfill_dependencies(
    cfg: Config, system: str | None = None, limit: int | None = None
) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn)
    if system:
        rows = [r for r in rows if r["system"] == system]
    if limit:
        rows = rows[:limit]

    modules = {
        "npm": npm,
        "pypi": pypi,
        "crates": crates,
        "maven": maven,
        "github": github_repo,
    }
    dependency_rows = 0
    with make_client(cfg) as client:
        for r in rows:
            module = modules.get(r["system"])
            if module is None:
                continue
            deps = module.fetch_dependencies(client, r["name"])
            versions = db.get_versions(conn, r["system"], r["name"])
            latest = max(
                versions, key=lambda v: v["published_at"] or "", default=None
            )
            payload = [
                (
                    r["system"], r["name"],
                    latest["version"] if latest else "",
                    r["system"], dep,
                )
                for dep in deps
            ]
            db.clear_package_dependencies(conn, r["system"], r["name"])
            if payload:
                db.upsert_dependencies(conn, payload)
                dependency_rows += len(payload)

    db.update_dependency_counts(conn)
    conn.close()
    return {"packages": len(rows), "dependency_rows": dependency_rows}


def backfill_licenses(
    cfg: Config,
    system: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn)
    if system:
        rows = [r for r in rows if r["system"] == system]
    if limit:
        rows = rows[:limit]

    updated = 0
    with make_client(cfg) as client:
        for r in rows:
            system_name, name = r["system"], r["name"]
            classifier = None
            if system_name == "pypi":
                doc = client.get_json(
                    f"https://pypi.org/pypi/{quote(name, safe='')}/json"
                )
                if doc:
                    classifier = pypi._classifier(doc.get("info") or {})
            repo_license = (
                forge.fetch_repo_license(
                    client, r["repo_url"], cfg.github_token, cfg.gitlab_token,
                    use_cache=not refresh,
                )
                if r["repo_url"]
                else None
            )
            if classifier is not None or repo_license is not None:
                db.update_license_sources(
                    conn, system_name, name,
                    classifier=classifier, repo_license=repo_license,
                )
                updated += 1

    conn.close()
    return {"packages": len(rows), "updated": updated}


def prioritize_impact(
    cfg: Config,
    system: str | None = None,
    limit: int = 50,
    missing_deps_limit: int = 200,
) -> dict:
    conn = _open(cfg)
    where = ["p.downloads_weekly > 0"]
    params: list[object] = []
    if system:
        where.append("p.system = ?")
        params.append(system)
    rows = conn.execute(
        f"""SELECT p.system, p.name, p.downloads_weekly, p.fan_in_transitive,
                   i.dependent_count
            FROM packages p
            LEFT JOIN package_impact i
              ON i.system = p.system AND i.name = p.name
            WHERE {' AND '.join(where)}""",
        params,
    ).fetchall()
    ranked = sorted(
        (
            {
                **dict(row),
                "impact_score": impact_score(
                    row["dependent_count"],
                    row["downloads_weekly"],
                    row["fan_in_transitive"],
                ),
            }
            for row in rows
        ),
        key=lambda row: row["impact_score"],
        reverse=True,
    )[:limit]

    dep_where = ["dp.name IS NULL"]
    dep_params: list[object] = []
    if system:
        dep_where.append("d.dep_system = ?")
        dep_params.append(system)
    deps = conn.execute(
        f"""SELECT d.dep_system AS system, d.dep_name AS name,
                   COUNT(*) AS uses,
                   SUM(COALESCE(i.dependent_count, 0)) AS parent_dependents,
                   SUM(COALESCE(p.downloads_weekly, 0)) AS parent_downloads
            FROM dependencies d
            JOIN packages p ON p.system = d.system AND p.name = d.name
            LEFT JOIN package_impact i
              ON i.system = p.system AND i.name = p.name
            LEFT JOIN packages dp
              ON dp.system = d.dep_system AND dp.name = d.dep_name
            WHERE {' AND '.join(dep_where)}
            GROUP BY d.dep_system, d.dep_name
            ORDER BY parent_dependents DESC, uses DESC, name ASC
            LIMIT ?""",
        [*dep_params, missing_deps_limit],
    ).fetchall()
    conn.close()

    paths: list[str] = []
    if deps:
        base = Path(cfg.data_dir) / "mvp" / "seeds"
        base.mkdir(parents=True, exist_ok=True)
        for dep_system in sorted({row["system"] for row in deps}):
            names = [row["name"] for row in deps if row["system"] == dep_system]
            path = base / f"impact-deps-{dep_system}.txt"
            path.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
            paths.append(str(path))

    return {
        "top": ranked,
        "missing_dependency_candidates": [dict(row) for row in deps],
        "seed_files": paths,
    }


def enrich_scorecard(
    cfg: Config,
    system: str | None = None,
    limit: int = 500,
) -> dict:
    conn = _open(cfg)
    where = [
        "r.repo_url IS NOT NULL", "r.repo_url != ''",
        "r.scorecard_checks_json IS NULL",
    ]
    params: list[object] = []
    if system:
        where.append("r.system = ?")
        params.append(system)
    rows = conn.execute(
        f"""SELECT r.system, r.name, r.repo_url, p.downloads_weekly
            FROM repo_stats r
            LEFT JOIN packages p ON p.system = r.system AND p.name = r.name
            WHERE {' AND '.join(where)}
            ORDER BY p.downloads_weekly DESC LIMIT ?""",
        [*params, limit],
    ).fetchall()
    updated = 0
    with make_client(cfg) as client:
        for row in rows:
            score, checks = fetch_scorecard(client, row["repo_url"])
            if score is None and checks is None:
                continue
            db.update_repo_scorecard(conn, row["system"], row["name"], score, checks)
            updated += 1
    conn.close()
    return {"requested": len(rows), "updated": updated}


def enrich_findings(
    cfg: Config,
    system: str | None = None,
    limit: int = 500,
) -> dict:
    conn = _open(cfg)
    where = ["f.name IS NULL", "p.downloads_weekly > 0"]
    params: list[object] = []
    if system:
        where.append("p.system = ?")
        params.append(system)
    rows = conn.execute(
        f"""SELECT p.system, p.name,
                   (SELECT v.version FROM versions v
                    WHERE v.system = p.system AND v.name = p.name
                    ORDER BY COALESCE(v.published_at, '') DESC LIMIT 1) AS version
            FROM packages p
            LEFT JOIN package_findings f
              ON f.system = p.system AND f.name = p.name
            WHERE {' AND '.join(where)}
            ORDER BY p.downloads_weekly DESC, p.fan_in_transitive DESC
            LIMIT ?""",
        [*params, limit],
    ).fetchall()
    updated = 0
    with make_client(cfg) as client:
        for row in rows:
            doc = findings.fetch_findings(
                client, row["system"], row["name"], row["version"]
            )
            if doc is None:
                continue
            db.upsert_findings(
                conn,
                [(
                    row["system"], row["name"], row["version"],
                    json.dumps(doc, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                )],
            )
            updated += 1
    conn.close()
    return {"requested": len(rows), "updated": updated}


def enrich_impact(
    cfg: Config,
    system: str | None = None,
    limit: int = 500,
) -> dict:
    conn = _open(cfg)
    where = ["i.name IS NULL", "p.downloads_weekly > 0"]
    params: list[object] = []
    if system:
        where.append("p.system = ?")
        params.append(system)
    rows = conn.execute(
        f"""SELECT p.system, p.name, p.downloads_weekly,
                   (SELECT v.version FROM versions v
                    WHERE v.system = p.system AND v.name = p.name
                    ORDER BY COALESCE(v.published_at, '') DESC LIMIT 1) AS version
            FROM packages p
            LEFT JOIN package_impact i
              ON i.system = p.system AND i.name = p.name
            WHERE {' AND '.join(where)}
            ORDER BY p.downloads_weekly DESC, p.fan_in_transitive DESC
            LIMIT ?""",
        [*params, limit],
    ).fetchall()
    updated = 0
    with make_client(cfg) as client:
        for row in rows:
            if not row["version"]:
                continue
            impact = depsdev.fetch_dependents(
                client, row["system"], row["name"], row["version"]
            )
            if impact is None:
                continue
            db.upsert_impact(
                conn,
                [(
                    row["system"], row["name"], row["version"],
                    impact["dependent_count"], impact["direct_dependent_count"],
                    impact["indirect_dependent_count"], "deps.dev",
                    datetime.now(timezone.utc).isoformat(),
                )],
            )
            updated += 1
    conn.close()
    return {"requested": len(rows), "updated": updated}


def enrich_github(
    cfg: Config,
    system: str | None = None,
    limit: int = 100,
    pages: int = 2,
) -> dict:
    conn = _open(cfg)
    params: list[str] = []
    where = [
        "p.repo_url IS NOT NULL",
        "p.repo_url != ''",
        "r.name IS NULL",
    ]
    if system:
        where.append("p.system = ?")
        params.append(system)
    rows = conn.execute(
        f"""SELECT p.system, p.name, p.repo_url, COALESCE(s.score, 0) AS score
            FROM packages p
            LEFT JOIN repo_stats r
              ON r.system = p.system AND r.name = p.name
            LEFT JOIN scores s
              ON s.system = p.system AND s.name = p.name
             AND s.model_version = ?
            WHERE {' AND '.join(where)}
            ORDER BY score DESC, p.downloads_weekly DESC
            LIMIT ?""",
        [cfg.model_version, *params, limit],
    ).fetchall()

    repos = 0
    commits = 0
    with make_client(cfg) as client:
        for row in rows:
            stats = forge.fetch_repo_stats(
                client, row["system"], row["name"], row["repo_url"],
                cfg.github_token, cfg.gitlab_token,
            )
            if stats is None:
                continue
            if github.parse_github_repo(row["repo_url"]):
                stats.scorecard_score, stats.scorecard_checks_json = fetch_scorecard(
                    client, row["repo_url"]
                )
            db.upsert_repo_stats(conn, [stats])
            repos += 1
            package_commits = forge.fetch_commits(
                client, row["repo_url"], cfg.github_token, cfg.gitlab_token,
                pages=pages,
            )
            if package_commits:
                db.upsert_commits(
                    conn,
                    [
                        (
                            row["system"], row["name"], c["sha"], c["committed_at"],
                            c["author_login"], c["author_email"],
                        )
                        for c in package_commits
                    ],
                )
                commits += len(package_commits)
            conn.commit()

    conn.close()
    return {"requested": len(rows), "repos": repos, "commits": commits}


def backfill_osv(
    cfg: Config,
    system: str | None = None,
    limit: int = 500,
    malicious_only: bool = False,
) -> dict:
    conn = _open(cfg)
    rows = db.missing_osv_details(conn, system, limit, malicious_only)
    updated = 0
    with make_client(cfg) as client:
        for row in rows:
            detail = osv.fetch_vuln_detail(client, row["vuln_id"])
            if detail is None:
                continue
            affected_json = json.dumps(detail["affected"], sort_keys=True)
            db.update_osv_detail(
                conn, row["vuln_id"], affected_json,
                detail.get("summary"), detail.get("modified"),
            )
            updated += 1
    conn.close()
    return {"requested": len(rows), "updated": updated}


def backfill_commits(
    cfg: Config,
    system: str | None = None,
    name: str | None = None,
    until: str | None = None,
    pages: int = 2,
    limit: int | None = None,
) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn)
    if system:
        rows = [r for r in rows if r["system"] == system]
    if name:
        rows = [r for r in rows if r["name"] == name]
    if limit:
        rows = rows[:limit]

    total = 0
    with make_client(cfg) as client:
        for r in rows:
            if not r["repo_url"]:
                continue
            commits = forge.fetch_commits(
                client, r["repo_url"], cfg.github_token, cfg.gitlab_token,
                until=until, pages=pages,
            )
            if not commits:
                continue
            db.upsert_commits(
                conn,
                [
                    (
                        r["system"], r["name"], c["sha"], c["committed_at"],
                        c["author_login"], c["author_email"],
                    )
                    for c in commits
                ],
            )
            total += len(commits)

    conn.close()
    return {"packages": len(rows), "commits": total}


def backfill_snapshots(
    cfg: Config,
    source: str | None = None,
    limit: int | None = None,
) -> dict:
    conn = _open(cfg)

    if source:
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        elif path.suffix == ".json":
            records = json.loads(text)
        else:
            import csv

            records = []
            for row in csv.DictReader(text.splitlines()):
                records.append(
                    {
                        "system": row.get("system"),
                        "name": row.get("name"),
                        "captured_at": row.get("captured_at"),
                        "maintainers": [
                            item.strip()
                            for item in (row.get("maintainers") or "").split(";")
                            if item.strip()
                        ],
                    }
                )
        count = snapshots.import_snapshot_records(conn, records)
        conn.close()
        return {"source": source, "snapshots": count}

    rows = [r for r in db.list_packages(conn) if r["system"] == "pypi"]
    if limit:
        rows = rows[:limit]

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=180)
    floor = now - timedelta(days=365)
    count = 0
    with make_client(cfg) as client:
        for r in rows:
            doc = client.get_json(
                f"https://pypi.org/pypi/{quote(r['name'], safe='')}/json"
            )
            if not doc:
                continue
            candidates = []
            for version, files in (doc.get("releases") or {}).items():
                times = [
                    f.get("upload_time_iso_8601") or f.get("upload_time")
                    for f in (files or [])
                ]
                times = [t for t in times if t]
                if not times:
                    continue
                published = parse_ts(min(times))
                if published is not None and floor <= published <= cutoff:
                    candidates.append((published, version, files))
            candidates.sort(key=lambda item: item[0], reverse=True)
            for published, _version, files in candidates:
                identities: list[str] = []
                for file_info in files[:3]:
                    url = file_info.get("url")
                    if not url:
                        continue
                    metadata = client.get_text(url + ".metadata")
                    if metadata:
                        identities = snapshots.parse_metadata_identities(metadata)
                        if identities:
                            break
                if identities:
                    payload = json.dumps(sorted(set(identities)), sort_keys=True)
                    db.record_snapshot(
                        conn,
                        "pypi",
                        r["name"],
                        published.isoformat(),
                        payload,
                        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    )
                    count += 1
                    break

    conn.commit()
    conn.close()
    return {"packages": len(rows), "snapshots": count}


def maintain(
    cfg: Config,
    with_commits: bool = True,
    limit: int | None = None,
    export: bool = True,
) -> dict:
    results: dict = {}
    results["deps"] = backfill_dependencies(cfg, limit=limit)
    results["licenses"] = backfill_licenses(cfg, limit=limit)
    if with_commits:
        results["commits"] = backfill_commits(cfg, limit=limit)
    results["resolve"] = resolve_all(cfg, limit=limit)
    results["snapshots"] = record_current_snapshots(cfg, limit=limit)
    results["scores"] = score_all(cfg)

    if export:
        exported = {}
        for fmt in ("parquet", "csv", "json", "spdx", "cyclonedx", "osv"):
            path, count = export_dataset(cfg, fmt)
            exported[fmt] = {"path": str(path), "records": count}
        results["export"] = exported
        path, count = build_report(cfg)
        results["report"] = {"path": str(path), "records": count}

    return results


def record_current_snapshots(
    cfg: Config, system: str | None = None, limit: int | None = None
) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn, system)
    if limit:
        rows = rows[:limit]

    captured_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        identities = sorted(
            {
                maintainer["identity"]
                for maintainer in db.get_maintainers(
                    conn, row["system"], row["name"]
                )
                if maintainer["identity"]
            }
        )
        payload = json.dumps(identities, sort_keys=True)
        db.record_snapshot(
            conn,
            row["system"],
            row["name"],
            captured_at,
            payload,
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )
    conn.commit()
    conn.close()
    return {"packages": len(rows), "snapshots": len(rows)}


def resolve_all(cfg: Config, limit: int | None = None) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn)
    if limit:
        rows = rows[:limit]
    total_links = 0

    with make_client(cfg) as client:
        for r in rows:
            system, name = r["system"], r["name"]
            versions = _version_models(db.get_versions(conn, system, name))
            maintainers = _maintainer_models(db.get_maintainers(conn, system, name))
            links = resolve_package(
                conn, client, system, name, r["repo_url"], maintainers, versions,
                token=cfg.github_token,
                gitlab_token=cfg.gitlab_token,
                use_keybase=cfg.osint.keybase,
                use_github_email=cfg.osint.github_email,
                use_pypi_provenance=cfg.osint.pypi_provenance,
                use_gpg=cfg.osint.gpg,
            )
            total_links += len(links)

    conn.close()
    return {"packages": len(rows), "links": total_links}


def score_all(cfg: Config) -> dict:
    conn = _open(cfg)
    rows = db.list_packages(conn)
    top_cache: dict[str, list[str]] = {}
    scored = 0

    for r in rows:
        system, name = r["system"], r["name"]
        if system not in top_cache:
            top_cache[system] = db.top_names(
                conn, system, 5000, min_downloads=TARGET_MIN_DOWNLOADS
            )
        repo = db.get_repo_stats(conn, system, name)

        ctx = Context(
            conn=conn,
            system=system,
            name=name,
            downloads_weekly=int(r["downloads_weekly"] or 0),
            top_names=top_cache[system],
            license=r["license"],
            license_classifier=r["license_classifier"],
            license_repo=repo["license"] if repo else None,
            dependencies_count=int(r["dependencies_count"] or 0),
            fan_in_transitive=int(r["fan_in_transitive"] or 0),
            identity_mapping=identity_map(
                conn, system, name, cfg.min_identity_confidence
            ),
            automation_identities=cfg.automation_identities,
            automation_patterns=cfg.automation_patterns,
        )
        signals = compute_all(ctx)
        score, band, inputs_hash = compute_score(
            signals, cfg.weights, cfg.model_version
        )
        ts = computed_at()

        for signal_name, sig in signals.items():
            db.record_signal(
                conn, system, name, signal_name,
                round(sig.value, 4),
                band_for(sig.value * 100) if sig.applicable else "",
                json.dumps(sig.evidence, sort_keys=True),
                cfg.model_version, ts,
            )
        db.record_score(
            conn, system, name, score, band,
            cfg.model_version, inputs_hash, ts,
        )
        scored += 1

    conn.commit()
    conn.close()
    return {"scored": scored}


def alerts(
    cfg: Config,
    min_score: float = 40.0,
    signal: str | None = None,
    min_signal: float = 0.5,
    limit: int = 100,
) -> list[dict]:
    conn = _open(cfg)
    sql = """SELECT s.system, s.name, s.score, s.band,
                    p.downloads_weekly, p.osv_count, p.repo_url
             FROM scores s
             JOIN packages p ON p.system = s.system AND p.name = s.name
             WHERE s.model_version = ? AND s.score >= ?"""
    args: list[object] = [cfg.model_version, min_score]
    if signal:
        sql += """ AND EXISTS (
                     SELECT 1 FROM signals g
                     WHERE g.system = s.system AND g.name = s.name
                       AND g.signal_type = ? AND g.value >= ?)"""
        args.extend([signal, min_signal])
    sql += " ORDER BY s.score DESC, s.name ASC LIMIT ?"
    args.append(min(limit, 500))
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _webhook_payload(rule, alerts: list[dict], fmt: str = "generic") -> dict:
    summary = f"MaintainerWatch: {rule.name} matched {len(alerts)} package(s)"
    lines = [
        f"{item['system']}/{item['name']} score={item['score']} band={item['band']}"
        for item in alerts[:20]
    ]
    if fmt == "slack":
        return {"text": "\n".join([summary, *lines])}
    if fmt == "discord":
        return {"content": "\n".join([summary, *lines])}
    return {"rule": rule.name, "count": len(alerts), "text": summary, "alerts": alerts}


def _send_webhook(url: str, payload: dict, timeout: float) -> dict:
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        return {"ok": response.status_code < 400, "status_code": response.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _send_email(cfg: Config, recipient: str, rule, alerts: list[dict]) -> dict:
    smtp = cfg.alerts.smtp
    if not smtp.host or not smtp.sender:
        return {"ok": False, "error": "SMTP not configured"}
    password = os.environ.get(smtp.password_env)
    message = EmailMessage()
    message["Subject"] = f"MaintainerWatch alert: {rule.name} ({len(alerts)})"
    message["From"] = smtp.sender
    message["To"] = recipient
    body = "\n".join(
        f"{item['system']}/{item['name']} score={item['score']} band={item['band']}"
        for item in alerts
    )
    message.set_content(f"Rule {rule.name} matched {len(alerts)} packages.\n\n{body}")
    try:
        with smtplib.SMTP(smtp.host, smtp.port, timeout=cfg.alerts.timeout_s) as server:
            if smtp.use_tls:
                server.starttls()
            if smtp.username and password:
                server.login(smtp.username, password)
            server.send_message(message)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_alert_rules(
    cfg: Config,
    out: str | None = None,
    webhook: str | None = None,
    email: str | None = None,
    dry_run: bool = False,
) -> list[dict]:
    results = []
    for rule in cfg.alerts.rules:
        matched = alerts(
            cfg,
            min_score=rule.min_score,
            signal=rule.signal,
            min_signal=rule.min_signal,
            limit=rule.limit,
        )
        entry = {"rule": rule.name, "count": len(matched), "alerts": matched}
        if not dry_run and matched:
            target_webhook = webhook or rule.webhook or cfg.alerts.webhook
            if target_webhook:
                entry["webhook"] = _send_webhook(
                    target_webhook,
                    _webhook_payload(rule, matched, cfg.alerts.webhook_format),
                    cfg.alerts.timeout_s,
                )
            target_email = email or rule.email or cfg.alerts.email
            if target_email:
                entry["email"] = _send_email(cfg, target_email, rule, matched)
        results.append(entry)

    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def _failed_scorecard_checks(repo) -> list[str]:
    try:
        checks = json.loads(repo["scorecard_checks_json"] or "[]")
    except (TypeError, ValueError):
        return []
    critical = {
        "Dangerous-Workflow", "Binary-Artifacts", "Branch-Protection",
        "Code-Review", "Maintained", "Security-Policy", "Signed-Releases",
        "Token-Permissions", "Vulnerabilities",
    }
    return [
        item.get("name") for item in checks
        if isinstance(item, dict) and item.get("name") in critical
        and int(item.get("score") or 0) == 0
    ]


def scan(cfg: Config, system: str, name: str) -> dict | None:
    conn = _open(cfg)
    score_row = conn.execute(
        """SELECT * FROM scores WHERE system=? AND name=? AND model_version=?
           ORDER BY computed_at DESC LIMIT 1""",
        (system, name, cfg.model_version),
    ).fetchone()
    if not score_row:
        conn.close()
        return None
    signal_rows = conn.execute(
        """SELECT * FROM signals WHERE system=? AND name=? AND model_version=?""",
        (system, name, score_row["model_version"]),
    ).fetchall()
    pkg = db.get_package(conn, system, name)
    repo = db.get_repo_stats(conn, system, name)
    impact = db.get_impact(conn, system, name)
    deps = db.get_dependencies(conn, system, name)
    conn.close()

    signal_map = {
        row["signal_type"]: {
            "value": row["value"],
            "evidence": json.loads(row["evidence_json"] or "{}"),
        }
        for row in signal_rows
    }
    risk_type = risk_note = next_step = ""
    if score_row["band"] in {"medium", "high"}:
        risk_type, risk_note, next_step = describe_risk(signal_map)

    applicable_weight = sum(
        cfg.weights.get(row["signal_type"], 0)
        for row in signal_rows
        if row["band"]
    )
    total_weight = sum(
        cfg.weights.get(name, 0) for name in SIGNALS
    )
    return {
        "system": system,
        "name": name,
        "score": score_row["score"],
        "band": score_row["band"],
        "evidence_coverage": round(applicable_weight / total_weight, 4) if total_weight else 0.0,
        "risk_type": risk_type,
        "risk_note": risk_note,
        "next_step": next_step,
        "impact_score": impact_score(
            impact["dependent_count"] if impact else None,
            pkg["downloads_weekly"] if pkg else None,
            pkg["fan_in_transitive"] if pkg else None,
        ),
        "impact_tier": impact_tier(impact["dependent_count"] if impact else None),
        "model_version": score_row["model_version"],
        "inputs_hash": score_row["inputs_hash"],
        "computed_at": score_row["computed_at"],
        "context": {
            "downloads_weekly": int(pkg["downloads_weekly"] or 0) if pkg else 0,
            "osv_count": int(pkg["osv_count"] or 0) if pkg else 0,
            "repo_url": pkg["repo_url"] if pkg else None,
            "license": pkg["license"] if pkg else None,
            "license_classifier": pkg["license_classifier"] if pkg else None,
            "license_repo": repo["license"] if repo else None,
            "dependencies_count": int(pkg["dependencies_count"] or 0) if pkg else 0,
            "fan_in": int(pkg["fan_in"] or 0) if pkg else 0,
            "fan_in_transitive": int(pkg["fan_in_transitive"] or 0) if pkg else 0,
            "scorecard_score": repo["scorecard_score"] if repo else None,
            "repo_archived": bool(repo["archived"]) if repo else None,
            "repo_owner_type": repo["owner_type"] if repo else None,
            "repo_stars": int(repo["stars"] or 0) if repo else None,
            "repo_forks": int(repo["forks"] or 0) if repo else None,
            "repo_open_issues": int(repo["open_issues"] or 0) if repo else None,
            "scorecard_failed_checks": _failed_scorecard_checks(repo) if repo else None,
            "dependent_count": int(impact["dependent_count"] or 0) if impact else None,
            "direct_dependent_count": int(impact["direct_dependent_count"] or 0) if impact else None,
            "indirect_dependent_count": int(impact["indirect_dependent_count"] or 0) if impact else None,
            "dependencies": sorted({d["dep_name"] for d in deps}),
        },
        "signals": signal_map,
    }
