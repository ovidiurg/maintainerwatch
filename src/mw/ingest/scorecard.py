from __future__ import annotations

from .github import parse_github_repo
from .http import CachedClient

API = "https://api.securityscorecards.dev/projects/github.com"


def fetch_scorecard(client: CachedClient, repo_url: str | None) -> tuple[float | None, str | None]:
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return None, None
    owner, repo = parsed
    doc = client.get_json(f"{API}/{owner}/{repo}")
    if not doc:
        return None, None
    score = doc.get("score")
    try:
        value = float(score) if score is not None else None
    except (TypeError, ValueError):
        value = None
    checks = doc.get("checks")
    return value, (__import__("json").dumps(checks, sort_keys=True) if checks is not None else None)


def fetch_score(client: CachedClient, repo_url: str | None) -> float | None:
    return fetch_scorecard(client, repo_url)[0]
