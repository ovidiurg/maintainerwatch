from __future__ import annotations

from . import npm, pypi
from .http import CachedClient


def fetch_downloads(client: CachedClient, system: str, name: str) -> int:
    if system == "npm":
        return npm.fetch_downloads(client, name)
    if system == "pypi":
        return pypi.fetch_downloads(client, name)
    return 0