from __future__ import annotations

import re
from urllib.parse import quote

from ..models import RepoStats
from .http import CachedClient

HOSTS = {"codeberg.org", "code.haverbeke.berlin"}
_RE = re.compile(r"^(?:https?://|git@)(?P<host>[^/:]+)[/:](?P<path>[^#?]+)")


def parse_gitea_repo(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    match = _RE.search(url.strip())
    if not match:
        return None
    host = match.group("host").lower()
    if host not in HOSTS:
        return None
    path = match.group("path").strip("/").split("/-/")[0].split("#")[0].split("?")[0]
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return host, f"{parts[0]}/{parts[1]}"


def _headers(token: str | None) -> dict[str, str]:
    return {"Authorization": f"token {token}"} if token else {}


def _repo(client: CachedClient, host: str, path: str, token: str | None) -> dict | None:
    return client.get_json(
        f"https://{host}/api/v1/repos/{quote(path, safe='/')}",
        headers=_headers(token),
    )


def fetch_repo_stats(
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    token: str | None,
) -> RepoStats | None:
    target = parse_gitea_repo(repo_url)
    if not target:
        return None
    host, path = target
    repo = _repo(client, host, path, token)
    if not repo:
        return None
    commits = client.get_json(
        f"https://{host}/api/v1/repos/{quote(path, safe='/')}/commits?limit=100",
        headers=_headers(token),
    ) or []
    authors = []
    for commit in commits:
        author = ((commit.get("commit") or {}).get("author") or {})
        email = (author.get("email") or "").strip().lower()
        name_ = (author.get("name") or "").strip()
        if email or name_:
            authors.append(email or name_)
    total = len(authors)
    top = max((authors.count(author) for author in set(authors)), default=0)
    owner = (repo.get("owner") or {})
    return RepoStats(
        system=system,
        name=name,
        repo_url=repo.get("html_url") or repo_url,
        owner=owner.get("login") or owner.get("username"),
        owner_created_at=owner.get("created"),
        contributors_12m=len(set(authors)),
        top_author_share=round(top / total, 4) if total else 0.0,
        last_commit_at=repo.get("updated_at"),
        archived=bool(repo.get("archived")),
        stars=int(repo.get("stars_count") or 0),
        forks=int(repo.get("forks_count") or 0),
        open_issues=int(repo.get("open_issues_count") or 0),
    )


def fetch_commits(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    until: str | None = None,
    pages: int = 2,
) -> list[dict]:
    target = parse_gitea_repo(repo_url)
    if not target:
        return []
    host, path = target
    out = []
    for page in range(1, pages + 1):
        url = f"https://{host}/api/v1/repos/{quote(path, safe='/')}/commits?limit=50&page={page}"
        if until:
            url += f"&until={quote(until, safe=':')}"
        batch = client.get_json(url, headers=_headers(token))
        if not isinstance(batch, list) or not batch:
            break
        for commit in batch:
            data = commit.get("commit") or {}
            author = data.get("author") or {}
            email = (author.get("email") or "").strip().lower() or None
            name_ = (author.get("name") or "").strip() or None
            out.append({
                "sha": commit.get("sha"),
                "committed_at": author.get("date") or commit.get("created"),
                "author_login": email or name_,
                "author_email": email,
            })
        if len(batch) < 50:
            break
    return out


def fetch_commit_emails(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    limit: int = 100,
) -> list[tuple[str, str]]:
    result = []
    for commit in fetch_commits(client, repo_url, token, pages=1)[:limit]:
        if commit["author_email"]:
            result.append((commit["author_email"], commit["author_login"] or ""))
    return result
