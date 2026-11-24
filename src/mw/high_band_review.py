from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, pipeline
from .config import Config


def build_packet(cfg: Config) -> dict[str, Any]:
    conn = db.connect(cfg.db_path)
    rows = conn.execute(
        """SELECT system, name, score, band FROM scores
           WHERE model_version=? AND band='high'
           ORDER BY score DESC, system, name""",
        (cfg.model_version,),
    ).fetchall()
    conn.close()

    packages = []
    for row in rows:
        detail = pipeline.scan(cfg, row["system"], row["name"])
        if detail is None:
            continue
        provider = detail.get("provider_context") or {}
        packages.append({
            "system": detail["system"],
            "name": detail["name"],
            "score": detail["score"],
            "band": detail["band"],
            "evidence_coverage": detail["evidence_coverage"],
            "risk_type": detail["risk_type"],
            "downloads_weekly": detail["context"]["downloads_weekly"],
            "osv_count": detail["context"]["osv_count"],
            "provider_context": {
                "osv": provider.get("osv"),
                "depsdev": provider.get("depsdev"),
                "scorecard": provider.get("scorecard"),
                "consensus": provider.get("consensus"),
            },
            "signal_context": detail.get("signal_context"),
            "top_signals": _top_signals(detail.get("signals") or {}, cfg.weights),
            "context": detail["context"],
            "review": {
                "status": "unreviewed",
                "reviewer": None,
                "reviewed_at": None,
                "notes": "",
                "evidence": [],
            },
        })
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": cfg.model_version,
        "count": len(packages),
        "packages": packages,
    }


def _top_signals(signals: dict[str, dict], weights: dict[str, int]) -> list[dict[str, Any]]:
    ranked = []
    for name, item in signals.items():
        value = float(item.get("value") or 0.0)
        if value <= 0:
            continue
        ranked.append((weights.get(name, 0) * value, value, name, item))
    ranked.sort(reverse=True)
    return [
        {"name": name, "value": round(value, 3), "evidence": item.get("evidence")}
        for _, value, name, item in ranked[:8]
    ]


def format_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# High-band review packet",
        "",
        f"Generated: {packet['generated_at']}",
        f"Model: {packet['model_version']}",
        f"Packages: {packet['count']}",
        "",
        "| Package | Score | Downloads | OSV | deps.dev | Repo | Status |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for pkg in packet["packages"]:
        provider = pkg["provider_context"]
        osv = (provider.get("osv") or {}).get("status", "unknown")
        depsdev = (provider.get("depsdev") or {}).get("status", "unknown")
        repo = pkg["context"].get("repo_url") or "none"
        lines.append(
            f"| `{pkg['system']}/{pkg['name']}` | {pkg['score']} | "
            f"{pkg['downloads_weekly']} | {osv} | {depsdev} | {repo} | "
            f"{pkg['review']['status']} |"
        )
    for pkg in packet["packages"]:
        provider = pkg["provider_context"]
        lines.extend([
            "",
            f"## {pkg['system']}/{pkg['name']}",
            "",
            f"- score: {pkg['score']}",
            f"- risk type: {pkg['risk_type'] or 'none'}",
            f"- confidence coverage: {pkg['evidence_coverage']}",
            f"- downloads/week: {pkg['downloads_weekly']}",
            f"- OSV: {(provider.get('osv') or {}).get('status')}",
            f"- deps.dev: {(provider.get('depsdev') or {}).get('status')}",
            f"- repo: {pkg['context'].get('repo_url') or 'none'}",
            f"- review: {pkg['review']['status']}",
        ])
        if pkg["top_signals"]:
            lines.append("- top signals:")
            for signal in pkg["top_signals"]:
                lines.append(f"  - {signal['name']}: {signal['value']}")
    return "\n".join(lines) + "\n"


def write_packet(packet: dict[str, Any], out_dir: str | Path, format: str = "both") -> list[Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    paths = []
    if format in {"json", "both"}:
        path = directory / f"high-band-{stamp}.json"
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        paths.append(path)
    if format in {"markdown", "both"}:
        path = directory / f"high-band-{stamp}.md"
        path.write_text(format_markdown(packet), encoding="utf-8")
        paths.append(path)
    return paths
