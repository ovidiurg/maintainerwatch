from __future__ import annotations

from urllib.parse import quote

from .http import CachedClient

API = "https://api.deps.dev/v3alpha"
SYSTEMS = {"npm": "npm", "pypi": "pypi", "crates": "cargo", "maven": "maven"}


def fetch_findings(
    client: CachedClient, system: str, name: str, version: str | None = None
) -> dict | None:
    ecosystem = SYSTEMS.get(system)
    if ecosystem is None:
        return None
    package = quote(name, safe="")
    if version:
        url = (
            f"{API}/systems/{ecosystem}/packages/{package}"
            f"/versions/{quote(version, safe='')}:findings"
        )
    else:
        url = f"{API}/systems/{ecosystem}/packages/{package}:findings"
    doc = client.get_json(url)
    return doc if isinstance(doc, dict) else None
