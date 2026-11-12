from __future__ import annotations

from ..models import IdentityLink, Version


def links_from_repo(
    system: str,
    name: str,
    repo_url: str,
    versions: list[Version],
) -> list[IdentityLink]:
    """Link a package to its declared source repository (MEDIUM confidence).

    PEP 740 provenance attestations identify the source repository/workflow.
    We do not attempt to map the workflow to a natural person here.
    """
    if not repo_url:
        return []
    has_provenance = any(v.has_provenance for v in versions)
    return [
        IdentityLink(
            system=system,
            name=name,
            id_a=f"{system}:{name}".lower(),
            id_b=repo_url.lower(),
            link_type="source_repo",
            confidence="medium" if has_provenance else "low",
            evidence_url=repo_url,
        )
    ]
