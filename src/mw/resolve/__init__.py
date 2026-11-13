from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from ..ingest.github import fetch_commit_emails
from ..ingest.http import CachedClient
from ..models import IdentityLink, Maintainer, Version
from . import github_email, gpg, keybase, pypi_provenance

CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_links(conn: sqlite3.Connection, links: Iterable[IdentityLink]) -> int:
    rows = []
    for link in links:
        rows.append(
            (
                link.system, link.name, link.id_a, link.id_b, link.link_type,
                link.confidence, link.evidence_url, link.observed_at or _now(),
            )
        )
    if not rows:
        return 0
    conn.executemany(
        """INSERT INTO identity_links
             (system, name, id_a, id_b, link_type, confidence, evidence_url, observed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(system, name, id_a, id_b, link_type) DO UPDATE SET
             confidence=excluded.confidence,
             evidence_url=COALESCE(excluded.evidence_url, identity_links.evidence_url),
             observed_at=excluded.observed_at""",
        rows,
    )
    conn.commit()
    return len(rows)


def resolve_package(
    conn: sqlite3.Connection,
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    maintainers: list[Maintainer],
    versions: list[Version],
    *,
    token: str | None,
    use_keybase: bool = True,
    use_github_email: bool = True,
    use_pypi_provenance: bool = True,
    use_gpg: bool = True,
) -> list[IdentityLink]:
    links: list[IdentityLink] = []

    if use_github_email:
        emails = {
            (v.publisher_email or "").strip().lower()
            for v in versions
            if v.publisher_email
        }
        links.extend(
            github_email.links_from_commits(
                client, system, name, repo_url, emails, token,
                owner=max((m.identity for m in maintainers if m.identity), default=None),
            )
        )

    if use_keybase:
        handles = {m.identity for m in maintainers if m.identity}
        handles.update(
            v.publisher_name for v in versions if v.publisher_name
        )
        for handle in sorted(handles)[:5]:
            links.extend(keybase.lookup(client, system, name, handle))

    if use_gpg:
        emails = {
            (v.publisher_email or "").strip().lower()
            for v in versions
            if v.publisher_email
        }
        emails.update(
            m.identity.strip().lower()
            for m in maintainers
            if m.identity and "@" in m.identity
        )
        for email in sorted(emails)[:5]:
            links.extend(gpg.lookup(client, system, name, email))

    if use_pypi_provenance and repo_url:
        links.extend(
            pypi_provenance.links_from_repo(system, name, repo_url, versions)
        )

    store_links(conn, links)
    return links


def identity_map(conn: sqlite3.Connection, system: str, name: str,
                 min_confidence: str = "medium") -> dict[str, str]:
    """Map raw identities to a canonical id, for links above a confidence level."""
    threshold = CONFIDENCE_RANK.get(min_confidence, 2)
    rows = conn.execute(
        "SELECT * FROM identity_links WHERE system=? AND name=?", (system, name)
    ).fetchall()

    graph: dict[str, set[str]] = {}
    for r in rows:
        if CONFIDENCE_RANK.get(r["confidence"], 0) < threshold:
            continue
        left = r["id_a"].strip().lower()
        right = r["id_b"].strip().lower()
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)

    mapping: dict[str, str] = {}
    visited: set[str] = set()
    for node in graph:
        if node in visited:
            continue
        component: set[str] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(graph.get(current, set()) - visited)
        canonical_id = min(component)
        for member in component:
            mapping[member] = canonical_id
    return mapping


def canonical(identity: str | None, mapping: dict[str, str]) -> str | None:
    if not identity:
        return None
    key = identity.strip().lower()
    return mapping.get(key, key)
