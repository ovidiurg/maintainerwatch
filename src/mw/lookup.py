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


def _diff_item(pkg: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": pkg.get("system"),
        "name": pkg.get("name"),
        "score": pkg.get("score"),
        "band": pkg.get("band"),
        "confidence": pkg.get("confidence"),
        "risk_type": pkg.get("risk_type"),
    }


def diff_indexes(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    before = old.get("packages") or {}
    after = new.get("packages") or {}
    added = []
    removed = []
    changed = []
    for key, pkg in after.items():
        previous = before.get(key)
        if previous is None:
            if pkg.get("band") in {"high", "medium"}:
                added.append(_diff_item(pkg))
            continue
        old_view = {
            "score": previous.get("score"),
            "band": previous.get("band"),
            "confidence": previous.get("confidence"),
            "coverage": previous.get("coverage"),
            "risk_type": previous.get("risk_type"),
            "top_signals": previous.get("top_signals"),
        }
        new_view = {
            "score": pkg.get("score"),
            "band": pkg.get("band"),
            "confidence": pkg.get("confidence"),
            "coverage": pkg.get("coverage"),
            "risk_type": pkg.get("risk_type"),
            "top_signals": pkg.get("top_signals"),
        }
        if old_view != new_view:
            old_band = previous.get("band")
            new_band = pkg.get("band")
            old_score = float(previous.get("score") or 0)
            new_score = float(pkg.get("score") or 0)
            if (
                old_band in {"high", "medium"}
                or new_band in {"high", "medium"}
                or abs(new_score - old_score) >= 5
            ):
                changed.append({"old": _diff_item(previous), "new": _diff_item(pkg)})
    for key, pkg in before.items():
        if key not in after and pkg.get("band") in {"high", "medium"}:
            removed.append(_diff_item(pkg))
    return {
        "old_generated_at": old.get("generated_at"),
        "new_generated_at": new.get("generated_at"),
        "old_model_version": old.get("model_version"),
        "new_model_version": new.get("model_version"),
        "added_high_medium": sorted(added, key=lambda item: (-float(item.get("score") or 0), str(item.get("name")))),
        "resolved_high_medium": sorted(removed, key=lambda item: str(item.get("name"))),
        "changed": sorted(changed, key=lambda item: str(item["new"].get("name"))),
    }


def format_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# MaintainerWatch index diff",
        "",
        f"Old: {diff.get('old_generated_at') or 'unknown'} · {diff.get('old_model_version') or '?'}",
        f"New: {diff.get('new_generated_at') or 'unknown'} · {diff.get('new_model_version') or '?'}",
        "",
        f"New high/medium: {len(diff.get('added_high_medium') or [])}",
        f"Resolved high/medium: {len(diff.get('resolved_high_medium') or [])}",
        f"Changed packages: {len(diff.get('changed') or [])}",
    ]
    for title, key in (
        ("New high/medium", "added_high_medium"),
        ("Resolved high/medium", "resolved_high_medium"),
    ):
        items = diff.get(key) or []
        if items:
            lines.extend(["", f"## {title}"])
            for item in items[:25]:
                lines.append(
                    f"- {item.get('system')}/{item.get('name')}: "
                    f"{item.get('band')} ({item.get('score')})"
                )
    changed = diff.get("changed") or []
    if changed:
        lines.extend(["", "## Changed"])
        for item in changed[:25]:
            old = item["old"]
            new = item["new"]
            lines.append(
                f"- {new.get('system')}/{new.get('name')}: "
                f"{old.get('band')} {old.get('score')} -> {new.get('band')} {new.get('score')}"
            )
    return "\n".join(lines) + "\n"
