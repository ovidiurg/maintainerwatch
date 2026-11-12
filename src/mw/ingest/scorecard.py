from __future__ import annotations

from .github import parse_github_repo
from .http import CachedClient

API = "https://api.securityscorecards.dev/projects/github.com"


def fetch_score(client: CachedClient, repo_url: str | None) -> float | None:
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    doc = client.get_json(f"{API}/{owner}/{repo}")
    if not doc:
        return None
    score = doc.get("score")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None
