from __future__ import annotations

from urllib.parse import quote

from .http import CachedClient

API = "https://api.deps.dev/v3alpha"
SYSTEMS = {"npm": "npm", "pypi": "pypi", "crates": "cargo", "maven": "maven"}


def fetch_dependents(
    client: CachedClient, system: str, name: str, version: str
) -> dict | None:
    ecosystem = SYSTEMS.get(system)
    if ecosystem is None:
        return None
    url = (
        f"{API}/systems/{ecosystem}/packages/{quote(name, safe='')}"
        f"/versions/{quote(version, safe='')}:dependents"
    )
    doc = client.get_json(url)
    if not isinstance(doc, dict):
        return None
    return {
        "dependent_count": int(doc.get("dependentCount") or 0),
        "direct_dependent_count": int(doc.get("directDependentCount") or 0),
        "indirect_dependent_count": int(doc.get("indirectDependentCount") or 0),
    }
