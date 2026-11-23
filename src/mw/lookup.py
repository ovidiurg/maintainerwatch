from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config
from .ingest.http import CachedClient

DEFAULT_INDEX_URL = (
    "https://github.com/ovidiurg/maintainerwatch/"
    "releases/latest/download/maintainerwatch-index.json"
)


class LookupError(RuntimeError):
    pass


def load_index(
    cfg: Config,
    source: str | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    if source:
        path = Path(source)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise LookupError(f"invalid index file: {path}") from exc
        url = source
    else:
        url = DEFAULT_INDEX_URL

    with CachedClient(cfg.data_dir / "cache", timeout_s=30.0, ttl_h=6) as client:
        doc = client.get_json(url, use_cache=not refresh)
    if not isinstance(doc, dict) or not isinstance(doc.get("packages"), dict):
        raise LookupError(f"could not load index: {url}")
    return doc


def find_package(doc: dict[str, Any], system: str, name: str) -> dict[str, Any] | None:
    packages = doc.get("packages") or {}
    direct = packages.get(f"{system}:{name}")
    if isinstance(direct, dict):
        return direct
    target = name.strip().lower()
    for pkg in packages.values():
        if not isinstance(pkg, dict):
            continue
        if str(pkg.get("system", "")).lower() != system.lower():
            continue
        if str(pkg.get("name", "")).strip().lower() == target:
            return pkg
    return None


def lookup(
    cfg: Config,
    system: str,
    name: str,
    source: str | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    doc = load_index(cfg, source, refresh=refresh)
    pkg = find_package(doc, system, name)
    if pkg is None:
        return {
            "found": False,
            "system": system,
            "name": name,
            "model_version": doc.get("model_version"),
            "generated_at": doc.get("generated_at"),
        }
    return {
        "found": True,
        **pkg,
        "model_version": doc.get("model_version"),
        "generated_at": doc.get("generated_at"),
    }


def format_text(result: dict[str, Any]) -> str:
    if not result.get("found"):
        return (
            f"No entry for {result.get('system')}/{result.get('name')} "
            f"in index {result.get('generated_at') or 'unknown date'}."
        )
    signals = result.get("top_signals") or []
    signal_text = ", ".join(
        f"{str(item.get('name', 'signal')).replace('_', ' ')} {float(item.get('value', 0)):.2f}"
        for item in signals
        if isinstance(item, dict)
    ) or "none"
    coverage = result.get("coverage")
    coverage_text = f"{round(float(coverage) * 100)}%" if coverage is not None else "unknown"
    return "\n".join([
        f"{result.get('system')}/{result.get('name')}",
        f"score: {result.get('score')}  band: {result.get('band')}",
        f"confidence: {result.get('confidence')}  coverage: {coverage_text}",
        f"risk type: {result.get('risk_type') or 'none'}",
        f"top signals: {signal_text}",
        f"model: {result.get('model_version')}  index: {result.get('generated_at')}",
        "static snapshot, not a live verdict or malware label",
    ])
