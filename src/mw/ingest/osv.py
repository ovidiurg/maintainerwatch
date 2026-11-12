from __future__ import annotations

from itertools import islice

from .http import CachedClient

OSV_QUERYBATCH = "https://api.osv.dev/v1/querybatch"
ECOSYSTEM = {"npm": "npm", "pypi": "PyPI", "crates": "crates.io", "maven": "Maven"}


def _chunks(iterable, size):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch


def fetch_vulns(
    client: CachedClient,
    packages: list[tuple[str, str]],
) -> dict[tuple[str, str], list[tuple[str, str | None, str | None]]]:
    """Return (system, name) -> [(vuln_id, severity, published_at)]."""
    out: dict[tuple[str, str], list[tuple[str, str | None, str | None]]] = {}
    supported = [(s, n) for s, n in packages if s in ECOSYSTEM]
    for s, n in packages:
        out[(s, n)] = []
    for batch in _chunks(supported, 500):
        queries = [
            {"package": {"name": name, "ecosystem": ECOSYSTEM.get(system, system)}}
            for system, name in batch
        ]
        doc = client.post_json(OSV_QUERYBATCH, {"queries": queries})
        results = (doc or {}).get("results") or []
        for (system, name), result in zip(batch, results):
            vulns = (result or {}).get("vulns") or []
            entries = []
            for v in vulns:
                severity = None
                sev = v.get("severity") or []
                if isinstance(sev, list) and sev:
                    severity = sev[0].get("score")
                db_sev = (v.get("database_specific") or {}).get("severity")
                entries.append((v.get("id"), severity or db_sev, v.get("published")))
            out[(system, name)] = entries
    return out
