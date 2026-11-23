from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__, db
from .config import Config
from .risk import describe_risk, has_high_confidence
from .signals import SIGNALS


def _top_signals(signal_map: dict[str, dict], weights: dict[str, int], limit: int = 3) -> list[dict[str, Any]]:
    ranked = []
    for name, item in signal_map.items():
        value = float(item.get("value") or 0.0)
        if not item.get("applicable") or value <= 0:
            continue
        ranked.append((weights.get(name, 0) * value, value, name))
    ranked.sort(reverse=True)
    return [
        {"name": name, "value": round(value, 2)}
        for _, value, name in ranked[:limit]
    ]


def build_index(conn, cfg: Config) -> dict[str, Any]:
    signal_rows = conn.execute(
        "SELECT system, name, signal_type, value, band, evidence_json "
        "FROM signals WHERE model_version=?",
        (cfg.model_version,),
    ).fetchall()
    signals: dict[tuple[str, str], dict[str, dict]] = {}
    for row in signal_rows:
        signals.setdefault((row["system"], row["name"]), {})[row["signal_type"]] = {
            "value": float(row["value"] or 0.0),
            "applicable": bool(row["band"]),
            "evidence": json.loads(row["evidence_json"] or "{}"),
        }

    score_rows = conn.execute(
        "SELECT system, name, score, band FROM scores WHERE model_version=?",
        (cfg.model_version,),
    ).fetchall()
    package_rows = {}
    for row in conn.execute(
        "SELECT system, name FROM packages"
    ):
        package_rows[(row["system"], row["name"])] = True

    total_weight = sum(cfg.weights.get(name, 0) for name in SIGNALS)
    packages: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for row in score_rows:
        key = (row["system"], row["name"])
        if key not in package_rows:
            continue
        signal_map = signals.get(key, {})
        applicable_weight = sum(
            cfg.weights.get(name, 0)
            for name, item in signal_map.items()
            if item.get("applicable")
        )
        coverage = applicable_weight / total_weight if total_weight else 0.0
        confidence = (
            "high"
            if has_high_confidence(signal_map, row["system"])
            else "evidence-only"
        )
        risk_type = ""
        if row["band"] in {"medium", "high"}:
            risk_type = describe_risk(signal_map)[0]
        packages[f"{row['system']}:{row['name']}"] = {
            "system": row["system"],
            "name": row["name"],
            "score": row["score"],
            "band": row["band"],
            "confidence": confidence,
            "coverage": round(coverage, 4),
            "risk_type": risk_type,
            "top_signals": _top_signals(signal_map, cfg.weights),
        }
        counts[row["system"]] = counts.get(row["system"], 0) + 1

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,
        "model_version": cfg.model_version,
        "counts": {"packages": len(packages), **dict(sorted(counts.items()))},
        "packages": dict(sorted(packages.items())),
    }


def write_index(conn, cfg: Config, out: str | Path, checksum: bool = True) -> tuple[Path, int]:
    payload = build_index(conn, cfg)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    if checksum:
        import hashlib
        path.with_suffix(path.suffix + ".sha256").write_text(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n",
            encoding="utf-8",
        )
    return path, len(payload["packages"])
