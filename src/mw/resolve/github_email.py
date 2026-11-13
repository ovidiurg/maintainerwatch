from __future__ import annotations

from ..ingest import forge
from ..ingest.http import CachedClient
from ..models import IdentityLink


def links_from_commits(
    client: CachedClient,
    system: str,
    name: str,
    repo_url: str | None,
    emails: set[str],
    token: str | None,
    gitlab_token: str | None = None,
    owner: str | None = None,
) -> list[IdentityLink]:
    """Link a publisher email to a GitHub/GitLab login when it is in public commits."""
    if not repo_url or not emails:
        return []
    pairs = forge.fetch_commit_emails(client, repo_url, token, gitlab_token)
    email_to_logins: dict[str, set[str]] = {}
    for email, login in pairs:
        if email and login:
            email_to_logins.setdefault(email, set()).add(login)

    links: list[IdentityLink] = []
    for email in sorted(emails):
        logins = email_to_logins.get(email)
        if not logins:
            continue
        for login in sorted(logins):
            links.append(
                IdentityLink(
                    system=system,
                    name=name,
                    id_a=email,
                    id_b=f"github:{login}".lower(),
                    link_type="email",
                    confidence="high",
                    evidence_url=repo_url,
                )
            )
    return links
