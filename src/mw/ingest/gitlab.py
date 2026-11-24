from __future__ import annotations

import re
from urllib.parse import quote, urlparse

from ..models import RepoStats
from .http import CachedClient

HOSTS = {
    "gitlab.com", "www.gitlab.com",
    "gitlab.redox-os.org", "gitlab.gnome.org",
    "foss.heptapod.net", "gitlab.beecode.cn", "gitlab.websupport.sk",
}
_RE = re.compile(r"^(?:https?://|git@)(?P<host>[^/:]+)[/:](?P<path>[^#?]+)")


def _target(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    value = url.strip()
    if value.startswith(("gitlab:", "gitlab.com:")):
        value = "https://gitlab.com/" + value.split(":", 1)[1].lstrip("/")
    match = _RE.search(value)
    if match:
        host = match.group("host").lower()
        path = match.group("path")
    elif value.startswith(("http://", "https://", "git@")):
        return None
    else:
        host = "gitlab.com"
        path = value
    if host == "www.gitlab.com":
        host = "gitlab.com"
    if host not in HOSTS:
        return None
    path = path.strip("/").split("/-/")[0].split("#")[0].split("?")[0]
    if path.endswith(".git"):
        path = path[:-4]
    if path.count("/") < 1:
        return None
    return host, path


def parse_gitlab_repo(url: str | None) -> str | None:
    target = _target(url)
    return target[1] if target else None


def _api(host: str) -> str:
    return f"https://{host}/api/v4"


def _headers(token: str | None) -> dict[str, str]:
    return {"PRIVATE-TOKEN": token} if token else {}


def _project(
    client: CachedClient, host: str, path: str, token: str | None, use_cache: bool = True
) -> dict | None:
    return client.get_json(
        f"{_api(host)}/projects/{quote(path, safe='')}",
        headers=_headers(token),
        use_cache=use_cache,
    )


def fetch_repo_stats(
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    token: str | None,
) -> RepoStats | None:
    target = _target(repo_url)
    if not target:
        return None
    host, path = target
    headers = _headers(token)
    project = _project(client, host, path, token)
    if not project:
        return None
    project_id = project.get("id")
    contributors = client.get_json(
        f"{_api(host)}/projects/{project_id}/repository/contributors?per_page=100",
        headers=headers,
    ) or []
    total = 0
    top = 0
    count = 0
    for contributor in contributors:
        commits = int(contributor.get("commits") or 0)
        if commits <= 0:
            continue
        total += commits
        top = max(top, commits)
        count += 1
    share = (top / total) if total else 0.0
    namespace = project.get("namespace") or {}
    owner_created = None
    if namespace.get("kind") == "group":
        group = client.get_json(
            f"{_api(host)}/groups/{namespace.get('id')}", headers=headers
        )
        owner_created = (group or {}).get("created_at")
    elif namespace.get("kind") == "user":
        user = client.get_json(
            f"{_api(host)}/users/{namespace.get('id')}", headers=headers
        )
        owner_created = (user or {}).get("created_at")
    license_data = project.get("license") or {}
    license_name = (
        license_data.get("spdx_identifier")
        or license_data.get("nickname")
        or license_data.get("name")
    )
    return RepoStats(
        system=system,
        name=name,
        repo_url=project.get("web_url") or repo_url,
        owner=namespace.get("full_path") or namespace.get("name"),
        owner_created_at=owner_created,
        contributors_12m=count,
        top_author_share=round(share, 4),
        last_commit_at=project.get("last_activity_at"),
        scorecard_score=None,
        license=license_name,
    )


def fetch_repo_license(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    use_cache: bool = True,
) -> str | None:
    target = _target(repo_url)
    if not target:
        return None
    host, path = target
    project = _project(client, host, path, token, use_cache=use_cache)
    if not project:
        return None
    license_data = project.get("license") or {}
    return (
        license_data.get("spdx_identifier")
        or license_data.get("nickname")
        or license_data.get("name")
    )


def fetch_commits(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    until: str | None = None,
    pages: int = 2,
    per_page: int = 100,
) -> list[dict]:
    target = _target(repo_url)
    if not target:
        return []
    host, path = target
    headers = _headers(token)
    project = _project(client, host, path, token)
    if not project:
        return []
    project_id = project.get("id")
    out: list[dict] = []
    for page in range(1, pages + 1):
        url = (
            f"{_api(host)}/projects/{project_id}/repository/commits"
            f"?per_page={per_page}&page={page}"
        )
        if until:
            url += f"&until={quote(until, safe=':')}"
        commits = client.get_json(url, headers=headers)
        if not isinstance(commits, list) or not commits:
            break
        for commit in commits:
            email = (commit.get("author_email") or "").strip().lower() or None
            name_ = (commit.get("author_name") or "").strip() or None
            out.append({
                "sha": commit.get("id"),
                "committed_at": commit.get("created_at"),
                "author_login": email or name_,
                "author_email": email,
            })
        if len(commits) < per_page:
            break
    return out


def fetch_commit_emails(
    client: CachedClient,
    repo_url: str | None,
    token: str | None,
    limit: int = 100,
) -> list[tuple[str, str]]:
    out = []
    for commit in fetch_commits(client, repo_url, token, pages=1)[:limit]:
        if commit["author_email"]:
            out.append((commit["author_email"], commit["author_login"] or ""))
    return out
