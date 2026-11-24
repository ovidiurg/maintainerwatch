from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scan_diff import (
    apply_waivers,
    load_index,
    load_waivers,
    lookup,
    manifest_system,
    parse_manifest,
    summary,
)

SKIP_DIRS = {
    ".git", ".venv", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".pytest_cache", "data",
}


def collect_manifests(root: str | Path = ".") -> list[dict[str, Any]]:
    root = Path(root)
    packages: dict[tuple[str, str], dict[str, Any]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        system = manifest_system(str(path))
        if not system:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_manifest(path.name, text)
        except (OSError, ValueError):
            continue
        for name, version in parsed.items():
            key = (system, name)
            item = packages.setdefault(key, {
                "system": system,
                "name": name,
                "version": version,
                "paths": [],
            })
            if version:
                item["version"] = version
            relative = str(path.relative_to(root))
            if relative not in item["paths"]:
                item["paths"].append(relative)
    return sorted(packages.values(), key=lambda item: (item["system"], item["name"]))


def build_report(
    root: str | Path,
    index_path: str | Path,
    waivers_path: str | Path | None = None,
) -> dict[str, Any]:
    index = load_index(index_path)
    packages = collect_manifests(root)
    findings = []
    unknown = []
    for package in packages:
        match = lookup(index, package["system"], package["name"])
        if not match:
            unknown.append(package)
            continue
        item = dict(match)
        item.update({
            "version": package["version"],
            "paths": package["paths"],
        })
        findings.append(item)
    if waivers_path:
        findings = apply_waivers(findings, load_waivers(waivers_path))
    payload = summary(findings, len(packages))
    payload.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "index_generated_at": index.get("generated_at"),
        "model_version": index.get("model_version"),
        "root": str(Path(root)),
        "unknown": unknown,
    })
    return payload


def render_html(report: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    rows = []
    for item in report["findings"]:
        band = str(item.get("band") or "unknown")
        status = "waived" if item.get("waived") else "active"
        signals = ", ".join(
            f"{signal.get('name')}={signal.get('value')}"
            for signal in (item.get("top_signals") or [])
            if isinstance(signal, dict)
        )
        rows.append(
            "<tr>"
            f"<td>{esc(item.get('system'))}/{esc(item.get('name'))}</td>"
            f"<td>{esc(item.get('version'))}</td>"
            f"<td><span class=\"band {esc(band)}\">{esc(band)}</span></td>"
            f"<td>{esc(item.get('score'))}</td>"
            f"<td>{esc(item.get('confidence'))}</td>"
            f"<td>{esc(item.get('risk_type') or '')}</td>"
            f"<td>{esc(signals)}</td>"
            f"<td>{esc(status)}</td>"
            "</tr>"
        )
    bands = ", ".join(f"{key}: {value}" for key, value in report["bands"].items()) or "none"
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MaintainerWatch team report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #17202a; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #dfe4ea; padding: .55rem; text-align: left; vertical-align: top; }}
th {{ background: #f7f8fa; }}
.band {{ padding: .1rem .45rem; border-radius: 999px; text-transform: uppercase; font-size: .78rem; }}
.high {{ background: #fde8e7; color: #a61b1b; }}
.medium {{ background: #fff3cd; color: #7a4b00; }}
.low {{ background: #e8f5ec; color: #17632f; }}
</style>
</head>
<body>
<h1>MaintainerWatch team report</h1>
<p>Root: {esc(report["root"])}<br>
Generated: {esc(report["generated_at"])}<br>
Index: {esc(report["index_generated_at"])} · model {esc(report["model_version"])}</p>
<p><strong>{len(report["findings"])}</strong> matched packages · {esc(bands)} · {report["waived"]} waived · {len(report["unknown"])} not in index</p>
<table>
<thead><tr><th>Package</th><th>Version</th><th>Band</th><th>Score</th><th>Confidence</th><th>Risk type</th><th>Top signals</th><th>Status</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body>
</html>
'''
