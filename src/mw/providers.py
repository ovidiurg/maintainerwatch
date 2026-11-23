from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import db
from .osv_match import affected


def _latest_version(conn: sqlite3.Connection, system: str, name: str) -> str | None:
    row = conn.execute(
        """SELECT version FROM versions
           WHERE system=? AND name=? AND COALESCE(is_yanked, 0)=0
           ORDER BY COALESCE(published_at, '') DESC, version DESC LIMIT 1""",
        (system, name),
    ).fetchone()
    return row["version"] if row else None


def _osv_context(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    version: str | None,
    rows: list[sqlite3.Row] | None = None,
) -> dict[str, Any]:
    if rows is None:
        rows = db.get_osv(conn, system, name)
    if not rows:
        return {"status": "none", "score": 0.0, "advisories": [], "reason": "no OSV records"}
    if not version:
        return {"status": "unknown", "score": None, "advisories": [], "reason": "no current version"}

    advisories = []
    has_unknown = False
    for row in rows:
        if row["affected_json"] is None:
            has_unknown = True
            matched = False
        else:
            matched = affected(row["affected_json"], system, name, version)
        if matched:
            advisories.append({
                "id": row["vuln_id"],
                "severity": row["severity"],
                "published_at": row["published_at"],
                "malicious": row["vuln_id"].startswith("MAL-"),
            })
    if advisories:
        malicious = any(item["malicious"] for item in advisories)
        return {
            "status": "affected",
            "score": 1.0 if malicious else 0.5,
            "current_version": version,
            "advisories": advisories,
        }
    if has_unknown:
        return {"status": "unknown", "score": None, "current_version": version, "advisories": [], "reason": "affected ranges missing"}
    return {"status": "not_affected", "score": 0.0, "current_version": version, "advisories": []}


def _depsdev_context(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    row: sqlite3.Row | None = None,
) -> dict[str, Any]:
    if row is None:
        row = db.get_findings(conn, system, name)
    if row is None:
        return {"status": "unavailable", "score": None, "findings": [], "reason": "no deps.dev findings record"}
    try:
        doc = json.loads(row["findings_json"] or "{}")
    except (TypeError, ValueError):
        return {"status": "unknown", "score": None, "findings": [], "reason": "invalid findings payload"}
    findings = []
    for key in ("packageFindings",):
        findings.extend(doc.get(key) or [])
    for key in ("requestedVersion", "defaultVersion"):
        findings.extend((doc.get(key) or {}).get("findings") or [])
    findings = [item for item in findings if isinstance(item, dict)]
    types = sorted({str(item.get("type")) for item in findings if item.get("type")})
    risks = sorted({str(item.get("risk")) for item in findings if item.get("risk")})
    score = 0.0
    if "MALICIOUS" in types:
        score = 1.0
    elif "VULNERABLE" in types:
        score = 0.5
    elif "DEPRECATED" in types:
        score = 0.4
    elif "LOW_USAGE" in types:
        score = 0.3
    elif "COOLDOWN" in types:
        score = 0.2
    elif findings:
        score = 0.2
    return {
        "status": "findings" if findings else "none",
        "score": score,
        "version": row["version"],
        "finding_types": types,
        "risks": risks,
        "findings": findings[:20],
    }


def _scorecard_context(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    repo: sqlite3.Row | None = None,
    trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if repo is None:
        repo = db.get_repo_stats(conn, system, name)
    if trend is None:
        trend = db.scorecard_trend(conn, system, name)
    if repo is None:
        return {"status": "unavailable", "score": None, "reason": "no repository stats", "trend": trend}
    score = repo["scorecard_score"]
    if score is None:
        return {"status": "unknown", "score": None, "reason": "no Scorecard score", "trend": trend}
    try:
        checks = json.loads(repo["scorecard_checks_json"] or "[]")
    except (TypeError, ValueError):
        checks = []
    failed = [
        item.get("name") for item in checks
        if isinstance(item, dict) and int(item.get("score") or 0) == 0
    ]
    return {
        "status": "available",
        "score": round(float(score), 2),
        "risk_score": round(max(0.0, min(1.0, (7.0 - float(score)) / 7.0)), 4),
        "failed_checks": failed[:20],
        "trend": trend,
    }


def build_context(conn: sqlite3.Connection, system: str, name: str) -> dict[str, Any] | None:
    package = db.get_package(conn, system, name)
    if package is None:
        return None
    version = _latest_version(conn, system, name)
    osv = _osv_context(conn, system, name, version)
    depsdev = _depsdev_context(conn, system, name)
    scorecard = _scorecard_context(conn, system, name)

    return _assemble_context(system, name, version, osv, depsdev, scorecard)


def _assemble_context(
    system: str,
    name: str,
    version: str | None,
    osv: dict[str, Any],
    depsdev: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    malicious = "MALICIOUS" in depsdev.get("finding_types", [])
    osv_affected = osv["status"] == "affected"
    if osv_affected or malicious:
        advisory = "confirmed"
    elif osv["status"] == "not_affected" and depsdev["status"] == "findings":
        advisory = "conflict"
    elif osv["status"] in {"unknown"} or depsdev["status"] == "unknown":
        advisory = "unknown"
    else:
        advisory = "none"

    available = sum(
        1 for item in (osv, depsdev, scorecard)
        if item["status"] not in {"unavailable", "unknown"}
    )
    conflicts = []
    if osv_affected and depsdev["status"] == "none":
        conflicts.append("OSV affected; deps.dev reports no findings")
    if not osv_affected and malicious:
        conflicts.append("deps.dev malicious; OSV does not confirm current version")

    return {
        "system": system,
        "name": name,
        "current_version": version,
        "osv": osv,
        "depsdev": depsdev,
        "scorecard": scorecard,
        "ecosyste_ms": {"status": "not_configured"},
        "consensus": {
            "advisory": advisory,
            "providers_available": available,
            "providers_expected": 3,
            "coverage": round(available / 3, 3),
            "conflicts": conflicts,
        },
    }


def bulk_context(
    conn: sqlite3.Connection,
    keys: list[tuple[str, str]],
    current_versions: dict[tuple[str, str], str | None] | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Build provider contexts in bulk for export/report paths."""
    unique = list(dict.fromkeys(keys))
    if not unique:
        return {}

    osv_map: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in conn.execute("SELECT * FROM osv"):
        osv_map.setdefault((row["system"], row["name"]), []).append(row)
    findings_map: dict[tuple[str, str], sqlite3.Row] = {}
    for row in conn.execute("SELECT * FROM package_findings"):
        findings_map[(row["system"], row["name"])] = row
    repo_map: dict[tuple[str, str], sqlite3.Row] = {}
    for row in conn.execute("SELECT * FROM repo_stats"):
        repo_map[(row["system"], row["name"])] = row
    history_map: dict[tuple[str, str], list[tuple[float, str]]] = {}
    for row in conn.execute(
        """SELECT system, name, observed_at, score FROM scorecard_history
           WHERE score IS NOT NULL ORDER BY observed_at"""
    ):
        history_map.setdefault((row["system"], row["name"]), []).append(
            (float(row["score"]), row["observed_at"])
        )

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key in unique:
        system, name = key
        version = (
            current_versions.get(key)
            if current_versions is not None
            else _latest_version(conn, system, name)
        )
        osv = _osv_context(conn, system, name, version, osv_map.get(key, []))
        depsdev = _depsdev_context(conn, system, name, findings_map.get(key))
        repo = repo_map.get(key)
        trend_rows = history_map.get(key, [])
        trend = (
            {
                "status": "available",
                "observations": len(trend_rows),
                "latest": round(float(trend_rows[-1][0]), 2),
                "previous": round(float(trend_rows[-2][0]), 2) if len(trend_rows) > 1 else None,
                "delta": (
                    round(float(trend_rows[-1][0]) - float(trend_rows[-2][0]), 2)
                    if len(trend_rows) > 1 else None
                ),
                "latest_at": trend_rows[-1][1],
            }
            if trend_rows
            else {"status": "unknown", "observations": 0}
        )
        scorecard = _scorecard_context(conn, system, name, repo, trend)
        out[key] = _assemble_context(system, name, version, osv, depsdev, scorecard)
    return out
