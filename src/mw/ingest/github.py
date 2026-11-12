from __future__ import annotations

import re
from collections import Counter

from ..models import RepoStats
from .http import CachedClient

API = "https://api.github.com"
_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#?]+)")


def parse_github_repo(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    m = _RE.search(url)
    if not m:
        return None
    owner = m.group("owner")
    repo = m.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _headers(token: str | None) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_repo_stats(
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    token: str | None,
) -> RepoStats | None:
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    headers = _headers(token)

    meta = client.get_json(f"{API}/repos/{owner}/{repo}", headers=headers)
    if not meta:
        return None

    owner_login = (meta.get("owner") or {}).get("login") or owner
    owner_created = (meta.get("owner") or {}).get("created_at")
    if not owner_created:
        user = client.get_json(f"{API}/users/{owner_login}", headers=headers)
        owner_created = (user or {}).get("created_at")

    contributors = client.get_json(
        f"{API}/repos/{owner}/{repo}/stats/contributors", headers=headers
    )
    total = 0
    top = 0
    n_contrib = 0
    if isinstance(contributors, list):
        for c in contributors:
            contributions = int(c.get("total") or 0)
            if contributions <= 0:
                continue
            total += contributions
            top = max(top, contributions)
            n_contrib += 1
    share = (top / total) if total else 0.0

    return RepoStats(
        system=system,
        name=name,
        repo_url=repo_url,
        owner=owner_login,
        owner_created_at=owner_created,
        contributors_12m=n_contrib,
        top_author_share=round(share, 4),
        last_commit_at=meta.get("pushed_at") or meta.get("updated_at"),
        scorecard_score=None,
    )


def fetch_commit_emails(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    limit: int = 100,
) -> list[tuple[str, str]]:
    """Return [(email, login)] from recent public commits."""
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return []
    owner, repo = parsed
    headers = _headers(token)
    commits = client.get_json(
        f"{API}/repos/{owner}/{repo}/commits?per_page={min(limit, 100)}",
        headers=headers,
    )
    out: list[tuple[str, str]] = []
    if isinstance(commits, list):
        for c in commits:
            commit = c.get("commit") or {}
            author = commit.get("author") or {}
            email = (author.get("email") or "").strip().lower()
            login = ((c.get("author") or {}).get("login") or "").strip()
            if email:
                out.append((email, login))
    return out


def author_counts(commit_pairs: list[tuple[str, str]]) -> Counter:
    return Counter(login or email for email, login in commit_pairs)
