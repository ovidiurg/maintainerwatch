from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import Config
from .ingest import downloads, npm, osv, pypi
from .ingest.github import fetch_repo_stats
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

    if system == "npm":
        fetch_top, fetch_package = npm.fetch_top, npm.fetch_package
    elif system == "pypi":
        fetch_top, fetch_package = pypi.fetch_top, pypi.fetch_package
    else:
        raise ValueError(f"unsupported system: {system}")

    packages = []
    versions: list[Version] = []
    maintainers: list[Maintainer] = []
    captured_at = datetime.now(timezone.utc).isoformat()

    with make_client(cfg) as client:
        names = fetch_top(client, top_n, seed_file)

        for name in names:
            result = fetch_package(client, name)
            if not result:
                continue
            pkg, pkg_versions, pkg_maintainers = result
            pkg.downloads_weekly = downloads.fetch_downloads(client, system, name)

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

        ctx = Context(
            conn=conn,
            system=system,
            name=name,
            downloads_weekly=int(r["downloads_weekly"] or 0),
            top_names=top_cache[system],
            identity_mapping=identity_map(
                conn, system, name, cfg.min_identity_confidence
            ),
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


def scan(cfg: Config, system: str, name: str) -> dict | None:
    conn = _open(cfg)
    score_row = conn.execute(
        """SELECT * FROM scores WHERE system=? AND name=?
           ORDER BY computed_at DESC LIMIT 1""",
        (system, name),
    ).fetchone()
    if not score_row:
        conn.close()
        return None
    signal_rows = conn.execute(
        """SELECT * FROM signals WHERE system=? AND name=? AND model_version=?""",
        (system, name, score_row["model_version"]),
    ).fetchall()
    conn.close()
    return {
        "system": system,
        "name": name,
        "score": score_row["score"],
        "band": score_row["band"],
        "model_version": score_row["model_version"],
        "inputs_hash": score_row["inputs_hash"],
        "computed_at": score_row["computed_at"],
        "signals": {
            r["signal_type"]: {
                "value": r["value"],
                "evidence": json.loads(r["evidence_json"] or "{}"),
            }
            for r in signal_rows
        },
    }
