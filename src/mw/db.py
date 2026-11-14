from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Maintainer, Package, RepoStats, Version

SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
  system TEXT NOT NULL, name TEXT NOT NULL, normalized TEXT,
  downloads_weekly INTEGER DEFAULT 0, osv_count INTEGER DEFAULT 0,
  repo_url TEXT, license TEXT, license_classifier TEXT, first_seen TEXT,
  dependencies_count INTEGER DEFAULT 0, fan_in INTEGER DEFAULT 0,
  fan_in_transitive INTEGER DEFAULT 0,
  PRIMARY KEY (system, name)
);

CREATE TABLE IF NOT EXISTS versions (
  system TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
  published_at TEXT, publisher_name TEXT, publisher_email TEXT,
  publisher_key_id TEXT,
  has_sig INTEGER DEFAULT 0, has_provenance INTEGER DEFAULT 0,
  is_yanked INTEGER DEFAULT 0, install_script TEXT,
  PRIMARY KEY (system, name, version)
);

CREATE TABLE IF NOT EXISTS maintainers (
  system TEXT NOT NULL, name TEXT NOT NULL, identity TEXT NOT NULL,
  role TEXT, source TEXT, account_created_at TEXT,
  first_seen TEXT, last_seen TEXT,
  PRIMARY KEY (system, name, identity, source)
);

CREATE TABLE IF NOT EXISTS repo_stats (
  system TEXT NOT NULL, name TEXT NOT NULL, repo_url TEXT,
  owner TEXT, owner_created_at TEXT, contributors_12m INTEGER DEFAULT 0,
  top_author_share REAL DEFAULT 0, last_commit_at TEXT, scorecard_score REAL,
  license TEXT, archived INTEGER DEFAULT 0, owner_type TEXT,
  stars INTEGER DEFAULT 0, forks INTEGER DEFAULT 0, open_issues INTEGER DEFAULT 0,
  scorecard_checks_json TEXT,
  PRIMARY KEY (system, name)
);

CREATE TABLE IF NOT EXISTS osv (
  system TEXT NOT NULL, name TEXT NOT NULL, vuln_id TEXT NOT NULL,
  severity TEXT, published_at TEXT, affected_json TEXT,
  summary TEXT, modified_at TEXT,
  PRIMARY KEY (system, name, vuln_id)
);

CREATE TABLE IF NOT EXISTS signals (
  system TEXT NOT NULL, name TEXT NOT NULL, signal_type TEXT NOT NULL,
  value REAL, band TEXT, evidence_json TEXT,
  model_version TEXT, computed_at TEXT,
  PRIMARY KEY (system, name, signal_type, model_version)
);

CREATE TABLE IF NOT EXISTS scores (
  system TEXT NOT NULL, name TEXT NOT NULL, score REAL, band TEXT,
  model_version TEXT, inputs_hash TEXT, computed_at TEXT,
  PRIMARY KEY (system, name, model_version)
);

CREATE TABLE IF NOT EXISTS snapshots (
  system TEXT NOT NULL, name TEXT NOT NULL, captured_at TEXT NOT NULL,
  maintainer_set_json TEXT, payload_hash TEXT,
  PRIMARY KEY (system, name, captured_at)
);

CREATE TABLE IF NOT EXISTS identity_links (
  system TEXT NOT NULL, name TEXT NOT NULL, id_a TEXT NOT NULL, id_b TEXT NOT NULL,
  link_type TEXT NOT NULL, confidence TEXT NOT NULL,
  evidence_url TEXT, observed_at TEXT,
  PRIMARY KEY (system, name, id_a, id_b, link_type)
);

CREATE TABLE IF NOT EXISTS dependencies (
  system TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
  dep_system TEXT NOT NULL, dep_name TEXT NOT NULL,
  PRIMARY KEY (system, name, version, dep_system, dep_name)
);

CREATE TABLE IF NOT EXISTS package_findings (
  system TEXT NOT NULL, name TEXT NOT NULL, version TEXT,
  findings_json TEXT, updated_at TEXT,
  PRIMARY KEY (system, name)
);

CREATE TABLE IF NOT EXISTS package_impact (
  system TEXT NOT NULL, name TEXT NOT NULL, version TEXT,
  dependent_count INTEGER, direct_dependent_count INTEGER,
  indirect_dependent_count INTEGER, source TEXT, updated_at TEXT,
  PRIMARY KEY (system, name)
);

CREATE TABLE IF NOT EXISTS commits (
  system TEXT NOT NULL, name TEXT NOT NULL, sha TEXT NOT NULL,
  committed_at TEXT, author_login TEXT, author_email TEXT,
  PRIMARY KEY (system, name, sha)
);

CREATE INDEX IF NOT EXISTS idx_versions_pkg ON versions (system, name, published_at);
CREATE INDEX IF NOT EXISTS idx_signals_pkg ON signals (system, name);
CREATE INDEX IF NOT EXISTS idx_scores_pkg ON scores (system, name);
CREATE INDEX IF NOT EXISTS idx_deps_dep ON dependencies (dep_system, dep_name);
CREATE INDEX IF NOT EXISTS idx_commits_pkg ON commits (system, name, committed_at);
CREATE INDEX IF NOT EXISTS idx_maintainers_identity ON maintainers (identity);
CREATE INDEX IF NOT EXISTS idx_versions_publisher_email ON versions (publisher_email);
CREATE INDEX IF NOT EXISTS idx_versions_publisher_name ON versions (publisher_name);
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_column(conn, "packages", "dependencies_count", "INTEGER DEFAULT 0")
    _ensure_column(conn, "packages", "fan_in", "INTEGER DEFAULT 0")
    _ensure_column(conn, "packages", "fan_in_transitive", "INTEGER DEFAULT 0")
    _ensure_column(conn, "packages", "license_classifier", "TEXT")
    _ensure_column(conn, "repo_stats", "license", "TEXT")
    _ensure_column(conn, "versions", "publisher_key_id", "TEXT")
    _ensure_column(conn, "versions", "install_script", "TEXT")
    _ensure_column(conn, "osv", "affected_json", "TEXT")
    _ensure_column(conn, "osv", "summary", "TEXT")
    _ensure_column(conn, "osv", "modified_at", "TEXT")
    _ensure_column(conn, "repo_stats", "archived", "INTEGER DEFAULT 0")
    _ensure_column(conn, "repo_stats", "owner_type", "TEXT")
    _ensure_column(conn, "repo_stats", "stars", "INTEGER DEFAULT 0")
    _ensure_column(conn, "repo_stats", "forks", "INTEGER DEFAULT 0")
    _ensure_column(conn, "repo_stats", "open_issues", "INTEGER DEFAULT 0")
    _ensure_column(conn, "repo_stats", "scorecard_checks_json", "TEXT")
    conn.commit()


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def upsert_packages(conn: sqlite3.Connection, packages: Iterable[Package]) -> None:
    rows = [
        (p.system, p.name, p.normalized or p.name.lower(), p.downloads_weekly,
         p.osv_count, p.repo_url, p.license, p.license_classifier, p.first_seen)
        for p in packages
    ]
    conn.executemany(
        """INSERT INTO packages
             (system, name, normalized, downloads_weekly, osv_count,
              repo_url, license, license_classifier, first_seen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name) DO UPDATE SET
             normalized=excluded.normalized,
             downloads_weekly=excluded.downloads_weekly,
             osv_count=excluded.osv_count,
             repo_url=COALESCE(excluded.repo_url, packages.repo_url),
             license=COALESCE(excluded.license, packages.license),
             license_classifier=COALESCE(excluded.license_classifier, packages.license_classifier),
             first_seen=COALESCE(excluded.first_seen, packages.first_seen)""",
        rows,
    )
    conn.commit()


def upsert_versions(conn: sqlite3.Connection, versions: Iterable[Version]) -> None:
    rows = [
        (v.system, v.name, v.version, v.published_at, v.publisher_name,
         v.publisher_email, v.publisher_key_id, int(v.has_sig),
         int(v.has_provenance), int(v.is_yanked), v.install_script)
        for v in versions
    ]
    conn.executemany(
        """INSERT INTO versions
             (system, name, version, published_at, publisher_name,
              publisher_email, publisher_key_id, has_sig, has_provenance, is_yanked,
              install_script)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, version) DO UPDATE SET
             published_at=COALESCE(excluded.published_at, versions.published_at),
             publisher_name=COALESCE(excluded.publisher_name, versions.publisher_name),
             publisher_email=COALESCE(excluded.publisher_email, versions.publisher_email),
             publisher_key_id=COALESCE(excluded.publisher_key_id, versions.publisher_key_id),
             has_sig=MAX(excluded.has_sig, versions.has_sig),
             has_provenance=MAX(excluded.has_provenance, versions.has_provenance),
             is_yanked=excluded.is_yanked,
             install_script=COALESCE(excluded.install_script, versions.install_script)""",
        rows,
    )
    conn.commit()


def upsert_maintainers(conn: sqlite3.Connection, maintainers: Iterable[Maintainer]) -> None:
    rows = [
        (m.system, m.name, m.identity, m.role, m.source,
         m.account_created_at, m.first_seen, m.last_seen)
        for m in maintainers
    ]
    conn.executemany(
        """INSERT INTO maintainers
             (system, name, identity, role, source, account_created_at, first_seen, last_seen)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, identity, source) DO UPDATE SET
             role=excluded.role,
             account_created_at=COALESCE(excluded.account_created_at, maintainers.account_created_at),
             first_seen=COALESCE(maintainers.first_seen, excluded.first_seen),
             last_seen=COALESCE(excluded.last_seen, maintainers.last_seen)""",
        rows,
    )
    conn.commit()


def upsert_repo_stats(conn: sqlite3.Connection, stats: Iterable[RepoStats]) -> None:
    rows = [
        (s.system, s.name, s.repo_url, s.owner, s.owner_created_at,
         s.contributors_12m, s.top_author_share, s.last_commit_at,
         s.scorecard_score, s.license, int(s.archived), s.owner_type,
         s.stars, s.forks, s.open_issues, s.scorecard_checks_json)
        for s in stats
    ]
    conn.executemany(
        """INSERT INTO repo_stats
             (system, name, repo_url, owner, owner_created_at,
              contributors_12m, top_author_share, last_commit_at,
              scorecard_score, license, archived, owner_type, stars, forks,
              open_issues, scorecard_checks_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name) DO UPDATE SET
             repo_url=COALESCE(excluded.repo_url, repo_stats.repo_url),
             owner=COALESCE(excluded.owner, repo_stats.owner),
             owner_created_at=COALESCE(excluded.owner_created_at, repo_stats.owner_created_at),
             contributors_12m=excluded.contributors_12m,
             top_author_share=excluded.top_author_share,
             last_commit_at=COALESCE(excluded.last_commit_at, repo_stats.last_commit_at),
             scorecard_score=COALESCE(excluded.scorecard_score, repo_stats.scorecard_score),
             license=COALESCE(excluded.license, repo_stats.license),
             archived=excluded.archived,
             owner_type=COALESCE(excluded.owner_type, repo_stats.owner_type),
             stars=excluded.stars,
             forks=excluded.forks,
             open_issues=excluded.open_issues,
             scorecard_checks_json=COALESCE(excluded.scorecard_checks_json, repo_stats.scorecard_checks_json)""",
        rows,
    )
    conn.commit()


def update_repo_scorecard(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    score: float | None,
    checks_json: str | None,
) -> None:
    conn.execute(
        """UPDATE repo_stats
           SET scorecard_score=COALESCE(?, scorecard_score),
               scorecard_checks_json=COALESCE(?, scorecard_checks_json)
           WHERE system=? AND name=?""",
        (score, checks_json, system, name),
    )
    conn.commit()


def upsert_osv(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.executemany(
        """INSERT INTO osv
             (system, name, vuln_id, severity, published_at,
              affected_json, summary, modified_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, vuln_id) DO UPDATE SET
             severity=COALESCE(excluded.severity, osv.severity),
             published_at=COALESCE(excluded.published_at, osv.published_at),
             affected_json=COALESCE(excluded.affected_json, osv.affected_json),
             summary=COALESCE(excluded.summary, osv.summary),
             modified_at=COALESCE(excluded.modified_at, osv.modified_at)""",
        list(rows),
    )
    conn.commit()


def get_osv(conn: sqlite3.Connection, system: str, name: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM osv WHERE system=? AND name=? ORDER BY vuln_id",
        (system, name),
    ).fetchall()


def missing_osv_details(
    conn: sqlite3.Connection,
    system: str | None,
    limit: int,
    malicious_only: bool = False,
) -> list[sqlite3.Row]:
    sql = "SELECT DISTINCT vuln_id FROM osv WHERE affected_json IS NULL"
    args: list[object] = []
    if system:
        sql += " AND system=?"
        args.append(system)
    if malicious_only:
        sql += " AND vuln_id LIKE 'MAL-%'"
    sql += " ORDER BY vuln_id LIMIT ?"
    args.append(limit)
    return conn.execute(sql, args).fetchall()


def update_osv_detail(
    conn: sqlite3.Connection,
    vuln_id: str,
    affected_json: str,
    summary: str | None,
    modified_at: str | None,
) -> int:
    cur = conn.execute(
        """UPDATE osv SET affected_json=?, summary=COALESCE(?, summary),
                         modified_at=COALESCE(?, modified_at)
           WHERE vuln_id=?""",
        (affected_json, summary, modified_at, vuln_id),
    )
    conn.commit()
    return cur.rowcount


def get_package(conn: sqlite3.Connection, system: str, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM packages WHERE system=? AND name=?", (system, name)
    ).fetchone()


def update_osv_counts(conn: sqlite3.Connection, counts: dict[tuple[str, str], int]) -> None:
    conn.executemany(
        "UPDATE packages SET osv_count=? WHERE system=? AND name=?",
        [(count, system, name) for (system, name), count in counts.items()],
    )
    conn.commit()


def update_license_sources(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    *,
    classifier: str | None = None,
    repo_license: str | None = None,
) -> None:
    if classifier is not None:
        conn.execute(
            "UPDATE packages SET license_classifier=? WHERE system=? AND name=?",
            (classifier, system, name),
        )
    if repo_license is not None:
        conn.execute(
            """INSERT INTO repo_stats (system, name, license) VALUES (?, ?, ?)
               ON CONFLICT(system, name) DO UPDATE SET license=excluded.license""",
            (system, name, repo_license),
        )
    conn.commit()


def record_snapshot(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    captured_at: str,
    maintainer_set_json: str,
    payload_hash: str,
) -> None:
    conn.execute(
        """INSERT INTO snapshots
             (system, name, captured_at, maintainer_set_json, payload_hash)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(system, name, captured_at) DO UPDATE SET
             maintainer_set_json=excluded.maintainer_set_json,
             payload_hash=excluded.payload_hash""",
        (system, name, captured_at, maintainer_set_json, payload_hash),
    )


def upsert_dependencies(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, str, str, str]],
) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO dependencies
             (system, name, version, dep_system, dep_name)
           VALUES (?, ?, ?, ?, ?)""",
        list(rows),
    )
    conn.commit()


def update_dependency_counts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE packages SET dependencies_count = (
             SELECT COUNT(DISTINCT dep_name) FROM dependencies d
             WHERE d.system = packages.system AND d.name = packages.name)"""
    )
    conn.execute(
        """UPDATE packages SET fan_in = (
             SELECT COUNT(DISTINCT d.name) FROM dependencies d
             WHERE d.dep_system = packages.system
               AND LOWER(d.dep_name) = LOWER(packages.name))"""
    )

    edges = conn.execute(
        """SELECT DISTINCT system, name, dep_system, dep_name FROM dependencies"""
    ).fetchall()
    reverse: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for edge in edges:
        key = (edge["dep_system"], edge["dep_name"].lower())
        reverse.setdefault(key, set()).add((edge["system"], edge["name"].lower()))

    nodes = conn.execute("SELECT system, name FROM packages").fetchall()
    updates = []
    for node in nodes:
        start = (node["system"], node["name"].lower())
        visited = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for parent in reverse.get(current, ()):
                if parent not in visited:
                    visited.add(parent)
                    stack.append(parent)
        updates.append((len(visited) - 1, node["system"], node["name"]))
    conn.executemany(
        "UPDATE packages SET fan_in_transitive=? WHERE system=? AND name=?",
        updates,
    )
    conn.commit()


def clear_dependencies(conn: sqlite3.Connection, system: str | None = None) -> None:
    if system:
        conn.execute("DELETE FROM dependencies WHERE system=?", (system,))
    else:
        conn.execute("DELETE FROM dependencies")
    conn.commit()


def clear_package_dependencies(
    conn: sqlite3.Connection, system: str, name: str
) -> None:
    conn.execute(
        "DELETE FROM dependencies WHERE system=? AND name=?", (system, name)
    )
    conn.commit()


def upsert_commits(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, str, str, str | None, str | None]],
) -> None:
    conn.executemany(
        """INSERT INTO commits
             (system, name, sha, committed_at, author_login, author_email)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, sha) DO UPDATE SET
             committed_at=excluded.committed_at,
             author_login=COALESCE(excluded.author_login, commits.author_login),
             author_email=COALESCE(excluded.author_email, commits.author_email)""",
        list(rows),
    )
    conn.commit()


def get_commits(
    conn: sqlite3.Connection, system: str, name: str
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM commits WHERE system=? AND name=?
           ORDER BY committed_at ASC""",
        (system, name),
    ).fetchall()


def clear_commits(
    conn: sqlite3.Connection, system: str | None = None, name: str | None = None
) -> None:
    if system and name:
        conn.execute(
            "DELETE FROM commits WHERE system=? AND name=?", (system, name)
        )
    elif system:
        conn.execute("DELETE FROM commits WHERE system=?", (system,))
    else:
        conn.execute("DELETE FROM commits")
    conn.commit()


def get_dependencies(conn: sqlite3.Connection, system: str, name: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM dependencies WHERE system=? AND name=?", (system, name)
    ).fetchall()


def get_snapshot_before(
    conn: sqlite3.Connection, system: str, name: str, cutoff_iso: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM snapshots
           WHERE system=? AND name=? AND captured_at <= ?
           ORDER BY captured_at DESC LIMIT 1""",
        (system, name, cutoff_iso),
    ).fetchone()


def get_latest_snapshot(
    conn: sqlite3.Connection, system: str, name: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM snapshots WHERE system=? AND name=?
           ORDER BY captured_at DESC LIMIT 1""",
        (system, name),
    ).fetchone()


def record_signal(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    signal_type: str,
    value: float,
    band: str,
    evidence_json: str,
    model_version: str,
    computed_at: str,
) -> None:
    conn.execute(
        """INSERT INTO signals
             (system, name, signal_type, value, band, evidence_json, model_version, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, signal_type, model_version) DO UPDATE SET
             value=excluded.value, band=excluded.band,
             evidence_json=excluded.evidence_json, computed_at=excluded.computed_at""",
        (system, name, signal_type, value, band, evidence_json, model_version, computed_at),
    )


def record_score(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    score: float,
    band: str,
    model_version: str,
    inputs_hash: str,
    computed_at: str,
) -> None:
    conn.execute(
        """INSERT INTO scores
             (system, name, score, band, model_version, inputs_hash, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, model_version) DO UPDATE SET
             score=excluded.score, band=excluded.band,
             inputs_hash=excluded.inputs_hash, computed_at=excluded.computed_at""",
        (system, name, score, band, model_version, inputs_hash, computed_at),
    )


def list_packages(conn: sqlite3.Connection, system: str | None = None) -> list[sqlite3.Row]:
    if system:
        return conn.execute(
            "SELECT * FROM packages WHERE system=? ORDER BY name", (system,)
        ).fetchall()
    return conn.execute("SELECT * FROM packages ORDER BY system, name").fetchall()


def get_versions(conn: sqlite3.Connection, system: str, name: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM versions WHERE system=? AND name=?
           ORDER BY COALESCE(published_at, '') ASC""",
        (system, name),
    ).fetchall()


def get_repo_stats(conn: sqlite3.Connection, system: str, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM repo_stats WHERE system=? AND name=?", (system, name)
    ).fetchone()


def get_maintainers(conn: sqlite3.Connection, system: str, name: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM maintainers WHERE system=? AND name=?", (system, name)
    ).fetchall()


def delete_package(conn: sqlite3.Connection, system: str, name: str) -> dict[str, int]:
    """Delete a package and all records keyed to it; returns affected counts."""
    counts: dict[str, int] = {}
    tables = (
        "versions", "maintainers", "repo_stats", "osv", "signals", "scores",
        "snapshots", "identity_links", "dependencies", "commits", "package_impact",
        "packages",
    )
    for table in tables:
        cur = conn.execute(
            f"DELETE FROM {table} WHERE system=? AND name=?", (system, name)
        )
        counts[table] = cur.rowcount
    cur = conn.execute(
        "DELETE FROM dependencies WHERE dep_system=? AND dep_name=?",
        (system, name),
    )
    counts["inbound_dependencies"] = cur.rowcount
    conn.commit()
    return counts


def upsert_findings(
    conn: sqlite3.Connection,
    rows: list[tuple],
) -> None:
    conn.executemany(
        """INSERT INTO package_findings
             (system, name, version, findings_json, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(system, name) DO UPDATE SET
             version=excluded.version,
             findings_json=excluded.findings_json,
             updated_at=excluded.updated_at""",
        rows,
    )
    conn.commit()


def get_findings(conn: sqlite3.Connection, system: str, name: str):
    return conn.execute(
        "SELECT * FROM package_findings WHERE system=? AND name=?", (system, name)
    ).fetchone()


def upsert_impact(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        """INSERT INTO package_impact
             (system, name, version, dependent_count, direct_dependent_count,
              indirect_dependent_count, source, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name) DO UPDATE SET
             version=excluded.version,
             dependent_count=excluded.dependent_count,
             direct_dependent_count=excluded.direct_dependent_count,
             indirect_dependent_count=excluded.indirect_dependent_count,
             source=excluded.source,
             updated_at=excluded.updated_at""",
        rows,
    )
    conn.commit()


def get_impact(conn: sqlite3.Connection, system: str, name: str):
    return conn.execute(
        "SELECT * FROM package_impact WHERE system=? AND name=?", (system, name)
    ).fetchone()


def get_identity_links(conn: sqlite3.Connection, system: str, name: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM identity_links WHERE system=? AND name=?", (system, name)
    ).fetchall()


def top_names(
    conn: sqlite3.Connection,
    system: str,
    limit: int = 5000,
    min_downloads: int = 0,
) -> list[str]:
    rows = conn.execute(
        """SELECT name FROM packages
           WHERE system=? AND downloads_weekly >= ?
           ORDER BY downloads_weekly DESC LIMIT ?""",
        (system, min_downloads, limit),
    ).fetchall()
    return [r["name"] for r in rows]
