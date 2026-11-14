from __future__ import annotations

import re
from collections import Counter
from urllib.parse import quote

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
    repo_license = (meta.get("license") or {}).get("spdx_id")
    if repo_license == "NOASSERTION":
        repo_license = None

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
        license=repo_license,
        archived=bool(meta.get("archived")),
        owner_type=(meta.get("owner") or {}).get("type"),
        stars=int(meta.get("stargazers_count") or 0),
        forks=int(meta.get("forks_count") or 0),
        open_issues=int(meta.get("open_issues_count") or 0),
    )


def fetch_repo_license(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    use_cache: bool = True,
) -> str | None:
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    meta = client.get_json(
        f"{API}/repos/{owner}/{repo}",
        headers=_headers(token),
        use_cache=use_cache,
    )
    if not meta:
        return None
    license_id = (meta.get("license") or {}).get("spdx_id")
    return None if license_id in (None, "NOASSERTION") else license_id


def fetch_commits(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    until: str | None = None,
    pages: int = 2,
    per_page: int = 100,
) -> list[dict]:
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return []
    owner, repo = parsed
    headers = _headers(token)
    until_param = until.replace("+00:00", "Z") if until else None

    out: list[dict] = []
    for page in range(1, pages + 1):
        url = f"{API}/repos/{owner}/{repo}/commits?per_page={per_page}&page={page}"
        if until_param:
            url += f"&until={quote(until_param, safe=':')}"
        commits = client.get_json(url, headers=headers)
        if not isinstance(commits, list) or not commits:
            break
        for commit in commits:
            data = commit.get("commit") or {}
            author = data.get("author") or {}
            committer = data.get("committer") or {}
            committed_at = author.get("date") or committer.get("date")
            sha = commit.get("sha")
            login = (commit.get("author") or {}).get("login")
            email = (author.get("email") or "").strip().lower() or None
            if sha and committed_at:
                out.append(
                    {
                        "sha": sha,
                        "committed_at": committed_at,
                        "author_login": login,
                        "author_email": email,
                    }
                )
        if len(commits) < per_page:
            break
    return out


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
