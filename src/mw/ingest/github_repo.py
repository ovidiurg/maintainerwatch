from __future__ import annotations

from pathlib import Path

from ..models import Maintainer, Package, Version
from .github import _headers, API, parse_github_repo
from .http import CachedClient

SEED_GITHUB = ["tukaani-project/xz"]


def normalize_name(name: str) -> str:
    return name.strip().lower()


def fetch_top(client: CachedClient, top_n: int, seed_file: str | None = None) -> list[str]:
    if seed_file:
        names = [
            line.strip()
            for line in Path(seed_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        names = list(SEED_GITHUB)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:top_n]


def fetch_package(
    client: CachedClient, name: str, token: str | None = None
) -> tuple[Package, list[Version], list[Maintainer]] | None:
    parsed = parse_github_repo(name)
    if not parsed:
        parts = name.strip().split("/")
        if len(parts) == 2 and all(parts):
            parsed = (parts[0], parts[1])
    if not parsed:
        return None
    owner, repo = parsed
    headers = _headers(token)

    meta = client.get_json(f"{API}/repos/{owner}/{repo}", headers=headers)
    if not meta:
        return None

    releases = client.get_json(
        f"{API}/repos/{owner}/{repo}/releases?per_page=100", headers=headers
    ) or []
    versions: list[Version] = []
    for release in releases:
        tag = release.get("tag_name")
        if not tag:
            continue
        author = (release.get("author") or {}).get("login")
        versions.append(
            Version(
                system="github",
                name=name,
                version=tag,
                published_at=release.get("published_at") or release.get("created_at"),
                publisher_name=author,
                has_sig=False,
                has_provenance=False,
                is_yanked=bool(release.get("draft")),
            )
        )

    # Fallback for repositories without GitHub releases: tags have no date here,
    # so release-based signals stay not applicable.
    if not versions:
        tags = client.get_json(
            f"{API}/repos/{owner}/{repo}/tags?per_page=100", headers=headers
        ) or []
        for tag in tags:
            if tag.get("name"):
                versions.append(
                    Version(system="github", name=name, version=tag["name"])
                )

    identities = {(meta.get("owner") or {}).get("login") or owner}
    identities.update(v.publisher_name for v in versions if v.publisher_name)
    maintainers = [
        Maintainer(system="github", name=name, identity=identity,
                   role="owner", source="github")
        for identity in sorted(identities)
    ]

    pkg = Package(
        system="github",
        name=name,
        normalized=normalize_name(name),
        downloads_weekly=0,
        repo_url=meta.get("html_url"),
        license=(meta.get("license") or {}).get("spdx_id"),
        first_seen=meta.get("created_at"),
    )
    return pkg, versions, maintainers


def fetch_dependencies(client: CachedClient, name: str) -> list[str]:
    return []
