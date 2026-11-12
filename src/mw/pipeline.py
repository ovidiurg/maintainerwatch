from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from . import db
from .config import Config
from .ingest import crates, downloads, github_repo, maven, npm, osv, pypi
from .ingest.github import fetch_repo_license, fetch_repo_stats
from .ingest.http import CachedClient
from .ingest.scorecard import fetch_score
from .models import Maintainer, Version
from .resolve import identity_map, resolve_package
from .score import band_for, compute_score, computed_at
from .signals import compute_all
from .signals.base import Context


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
                osv_rows.append((s, n, vuln_id, severity, published))
        db.upsert_osv(conn, osv_rows)
        db.update_osv_counts(conn, counts)
        conn.commit()

        github_count = 0
        if with_github:
            for pkg in packages:
                if not pkg.repo_url:
                    continue
                stats = fetch_repo_stats(
                    client, system, pkg.name, pkg.repo_url, cfg.github_token
                )
                if not stats:
                    continue
                stats.scorecard_score = fetch_score(client, pkg.repo_url)
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
                fetch_repo_license(
                    client, r["repo_url"], cfg.github_token,
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
                use_keybase=cfg.osint.keybase,
                use_github_email=cfg.osint.github_email,
                use_pypi_provenance=cfg.osint.pypi_provenance,
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
            top_cache[system] = db.top_names(conn, system, 5000)
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
    deps = db.get_dependencies(conn, system, name)
    conn.close()

    return {
        "system": system,
        "name": name,
        "score": score_row["score"],
        "band": score_row["band"],
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
            "scorecard_score": repo["scorecard_score"] if repo else None,
            "dependencies": sorted({d["dep_name"] for d in deps}),
        },
        "signals": {
            r["signal_type"]: {
                "value": r["value"],
                "evidence": json.loads(r["evidence_json"] or "{}"),
            }
            for r in signal_rows
        },
    }
