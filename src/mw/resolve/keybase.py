from __future__ import annotations

from urllib.parse import quote

from ..ingest.http import CachedClient
from ..models import IdentityLink

LOOKUP = "https://keybase.io/_/api/1.0/user/lookup.json"


def _them(doc: dict) -> dict | None:
    them = doc.get("them")
    if isinstance(them, list):
        return them[0] if them else None
    if isinstance(them, dict):
        return them or None
    return None


def lookup(client: CachedClient, system: str, name: str, handle: str) -> list[IdentityLink]:
    """Passive lookup of self-declared Keybase proofs (public, opt-in)."""
    if not handle or " " in handle or "@" in handle:
        return []
    doc = client.get_json(f"{LOOKUP}?username={quote(handle)}&fields=proofs_summary")
    if not isinstance(doc, dict):
        return []
    them = _them(doc)
    if not them:
        return []
    kb_username = (them.get("basics") or {}).get("username") or handle
    proofs = ((them.get("proofs_summary") or {}).get("all")) or []
    links: list[IdentityLink] = []
    for p in proofs:
        ptype = (p.get("proof_type") or "").strip().lower()
        nametag = (p.get("nametag") or "").strip()
        if not ptype or not nametag:
            continue
        if ptype not in {"github", "gitlab", "dns", "generic_web_site", "twitter"}:
            continue
        links.append(
            IdentityLink(
                system=system,
                name=name,
                id_a=f"keybase:{kb_username}".lower(),
                id_b=f"{ptype}:{nametag}".lower(),
                link_type="keybase_proof",
                confidence="high",
                evidence_url=f"https://keybase.io/{kb_username}",
            )
        )
    return links
