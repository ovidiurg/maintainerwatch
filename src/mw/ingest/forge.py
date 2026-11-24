from __future__ import annotations

from ..models import RepoStats
from . import gitea, github, gitlab
from .http import CachedClient


def detect_forge(repo_url: str | None) -> str | None:
    if github.parse_github_repo(repo_url):
        return "github"
    if gitea.parse_gitea_repo(repo_url):
        return "gitea"
    if gitlab.parse_gitlab_repo(repo_url):
        return "gitlab"
    return None


def fetch_repo_stats(
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    github_token: str | None = None,
    gitlab_token: str | None = None,
) -> RepoStats | None:
    if github.parse_github_repo(repo_url):
        return github.fetch_repo_stats(client, system, name, repo_url, github_token)
    if gitea.parse_gitea_repo(repo_url):
        return gitea.fetch_repo_stats(client, system, name, repo_url, None)
    if gitlab.parse_gitlab_repo(repo_url):
        return gitlab.fetch_repo_stats(client, system, name, repo_url, gitlab_token)
    return None


def fetch_repo_license(
    client: CachedClient,
    repo_url: str | None,
    github_token: str | None = None,
    gitlab_token: str | None = None,
    use_cache: bool = True,
) -> str | None:
    if github.parse_github_repo(repo_url):
        return github.fetch_repo_license(
            client, repo_url, github_token, use_cache=use_cache
        )
    if gitlab.parse_gitlab_repo(repo_url):
        return gitlab.fetch_repo_license(
            client, repo_url, gitlab_token, use_cache=use_cache
        )
    return None


def fetch_commits(
    client: CachedClient,
    repo_url: str | None,
    github_token: str | None = None,
    gitlab_token: str | None = None,
    until: str | None = None,
    pages: int = 2,
) -> list[dict]:
    if github.parse_github_repo(repo_url):
        return github.fetch_commits(
            client, repo_url, github_token, until=until, pages=pages
        )
    if gitea.parse_gitea_repo(repo_url):
        return gitea.fetch_commits(client, repo_url, None, until=until, pages=pages)
    if gitlab.parse_gitlab_repo(repo_url):
        return gitlab.fetch_commits(
            client, repo_url, gitlab_token, until=until, pages=pages
        )
    return []


def fetch_commit_emails(
    client: CachedClient,
    repo_url: str | None,
    github_token: str | None = None,
    gitlab_token: str | None = None,
    limit: int = 100,
) -> list[tuple[str, str]]:
    if github.parse_github_repo(repo_url):
        return github.fetch_commit_emails(
            client, repo_url, github_token, limit=limit
        )
    if gitea.parse_gitea_repo(repo_url):
        return gitea.fetch_commit_emails(client, repo_url, None, limit=limit)
    if gitlab.parse_gitlab_repo(repo_url):
        return gitlab.fetch_commit_emails(
            client, repo_url, gitlab_token, limit=limit
        )
    return []
