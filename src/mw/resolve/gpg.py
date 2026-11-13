from __future__ import annotations

from urllib.parse import quote

from ..ingest.http import CachedClient
from ..models import IdentityLink

KEYSERVER = "https://keyserver.ubuntu.com/pks/lookup"


def lookup(client: CachedClient, system: str, name: str, email: str) -> list[IdentityLink]:
    if not email or "@" not in email:
        return []
    url = f"{KEYSERVER}?op=index&search={quote(email)}&options=mr"
    text = client.get_text(url)
    if not text:
        return []

    lines = text.splitlines()
    if not any(
        line.startswith("uid:") and email.lower() in line.lower()
        for line in lines
    ):
        return []

    key_ids = []
    for line in lines:
        if not line.startswith("pub:"):
            continue
        parts = line.split(":")
        if len(parts) > 1 and parts[1]:
            key_ids.append(parts[1].lower())

    links = []
    for key_id in sorted(set(key_ids))[:5]:
        links.append(
            IdentityLink(
                system=system,
                name=name,
                id_a=email.lower(),
                id_b=f"gpg:{key_id}",
                link_type="gpg_key",
                confidence="high",
                evidence_url=url,
            )
        )
    return links
