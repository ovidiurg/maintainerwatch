from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from . import db
from .config import Config
from .impact import impact_tier
from .risk import describe_risk, has_high_confidence
from .signals import SIGNALS

INCIDENTS = [
    ("npm", "event-stream"),
    ("npm", "ua-parser-js"),
    ("npm", "colors"),
    ("npm", "node-ipc"),
    ("npm", "eslint-scope"),
    ("npm", "eslint-config-eslint"),
    ("npm", "coa"),
    ("npm", "rc"),
    ("github", "tukaani-project/xz"),
]

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MaintainerWatch report</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #1b1b1b; }
  h1 { margin-bottom: 0.2rem; }
  .muted { color: #666; }
  .cards { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 0.8rem 1.2rem; }
  .card b { font-size: 1.6rem; display: block; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }
  th, td { border-bottom: 1px solid #eee; padding: 0.4rem 0.6rem; text-align: left; }
  th { background: #fafafa; }
  .high { color: #b00020; font-weight: 600; }
  .medium { color: #b26a00; font-weight: 600; }
  .low { color: #2e7d32; }
  code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 3px; }
</style>
</head>
<body>
<h1>MaintainerWatch</h1>
<p class="muted">Open maintainer-level supply-chain risk. Generated {{ generated }} · model {{ model_version }}</p>

<div class="cards">
  <div class="card"><b>{{ total }}</b>packages scored</div>
  <div class="card"><b class="high">{{ bands.high }}</b>high risk</div>
  <div class="card"><b class="medium">{{ bands.medium }}</b>medium risk</div>
  <div class="card"><b class="low">{{ bands.low }}</b>low risk</div>
</div>

<h2>Top risk</h2>
<table>
  <tr><th>System</th><th>Package</th><th>Score</th><th>Band</th><th>Confidence</th><th>Coverage</th><th>Risk type</th><th>Short description</th><th>Next step</th><th>Downloads/wk</th><th>OSV</th><th>Fan-in</th><th>Fan-in trans.</th><th>Dependents</th><th>Impact</th><th>Scorecard</th><th>Repo</th></tr>
  {% for r in top %}
  <tr>
    <td>{{ r.system }}</td>
    <td>{{ r.name }}</td>
    <td>{{ r.score }}</td>
    <td class="{{ r.band }}">{{ r.band }}</td>
    <td class="{{ 'high' if r.confidence == 'high' else 'medium' }}">{{ r.confidence }}</td>
    <td>{{ "%.0f%%"|format(r.coverage * 100) }}</td>
    <td>{{ r.risk_type or "-" }}</td>
    <td>{{ r.risk_note or "-" }}</td>
    <td>{{ r.next_step or "-" }}</td>
    <td>{{ r.downloads_weekly or 0 }}</td>
    <td>{{ r.osv_count or 0 }}</td>
    <td>{{ r.fan_in or 0 }}</td>
    <td>{{ r.fan_in_transitive or 0 }}</td>
    <td>{{ r.dependent_count if r.dependent_count is not none else "-" }}</td>
    <td>{{ r.impact_tier }}</td>
    <td>{{ "%.1f"|format(r.scorecard_score) if r.scorecard_score is not none else "-" }}</td>
    <td>{% if r.repo_url %}<a href="{{ r.repo_url }}">source</a>{% endif %}</td>
  </tr>
  {% endfor %}
</table>

<h2>Historical incidents</h2>
<p class="muted">Replay check: packages involved in past takeover incidents, if present in this dataset.</p>
<table>
  <tr><th>System</th><th>Package</th><th>Score</th><th>Band</th><th>Risk type</th><th>Short description</th><th>Next step</th></tr>
  {% for r in incidents %}
  <tr><td>{{ r.system }}</td><td>{{ r.name }}</td><td>{{ r.score }}</td><td class="{{ r.band }}">{{ r.band }}</td><td>{{ r.risk_type or "-" }}</td><td>{{ r.risk_note or "-" }}</td><td>{{ r.next_step or "-" }}</td></tr>
  {% else %}
  <tr><td colspan="7" class="muted">No incident packages ingested yet.</td></tr>
  {% endfor %}
</table>

<h2>Method</h2>
<p>Score = 100 × Σ(weight × value) / Σ(weight) over applicable signals:
publisher_change (30), bus_factor (20), account_age (15), release_anomaly (10),
signing_gap (10), typosquat (10), license_inconsistency (5), commit_anomaly (15),
scorecard (10), dependency_risk (15), maintainer_continuity (15),
install_script (15), osv_risk (10), depsdev_findings (10). Bands: &lt;25 low,
&lt;50 medium, else high. A numerical high score is capped to medium unless one
high-confidence signal (publisher_change, commit_anomaly, osv_risk,
depsdev_findings, install_script or maintainer_continuity) is at least 0.5.
Confidence is `high` only when such a signal is present; otherwise the row is
`evidence-only`. Coverage is the applicable signal weight divided by the total
model weight. Identity-gated signals only use links with high/medium confidence. Risk type,
short description and next investigation step are shown for medium/high scores
and derived from the dominant signals.</p>
<p class="muted">Only public, role-related data is used. See docs/gdpr.md.</p>
</body>
</html>
"""


def build_report(cfg: Config, out: str | Path = "report.html") -> tuple[Path, int]:
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = conn.execute(
        """SELECT s.system, s.name, s.score, s.band,
                  p.downloads_weekly, p.osv_count, p.repo_url,
                  p.fan_in, p.fan_in_transitive, p.dependencies_count, p.license,
                  r.scorecard_score, i.dependent_count
           FROM scores s
           LEFT JOIN packages p ON p.system = s.system AND p.name = s.name
           LEFT JOIN repo_stats r ON r.system = s.system AND r.name = s.name
           LEFT JOIN package_impact i ON i.system = s.system AND i.name = s.name
           WHERE s.model_version = ?
           ORDER BY s.score DESC, s.name ASC""",
        (cfg.model_version,),
    ).fetchall()

    signal_rows = conn.execute(
        """SELECT system, name, signal_type, value, band, evidence_json
           FROM signals WHERE model_version = ?""",
        (cfg.model_version,),
    ).fetchall()
    conn.close()

    signals: dict[tuple[str, str], dict] = defaultdict(dict)
    for row in signal_rows:
        signals[(row["system"], row["name"])][row["signal_type"]] = {
            "value": row["value"],
            "evidence": json.loads(row["evidence_json"] or "{}"),
            "applicable": bool(row["band"]),
        }

    records = []
    for row in rows:
        record = dict(row)
        record["risk_type"] = ""
        record["risk_note"] = ""
        record["next_step"] = ""
        record["impact_tier"] = impact_tier(record.get("dependent_count"))
        signal_map = signals[(record["system"], record["name"])]
        record["confidence"] = (
            "high" if has_high_confidence(signal_map) else "evidence-only"
        )
        applicable_weight = sum(
            cfg.weights.get(name, 0)
            for name, signal in signal_map.items()
            if signal.get("applicable")
        )
        total_weight = sum(cfg.weights.get(name, 0) for name in SIGNALS)
        record["coverage"] = (
            applicable_weight / total_weight if total_weight else 0.0
        )
        if record["band"] in {"medium", "high"}:
            record["risk_type"], record["risk_note"], record["next_step"] = describe_risk(
                signals[(record["system"], record["name"])]
            )
        records.append(record)
    bands = {"low": 0, "medium": 0, "high": 0}
    for r in records:
        bands[r["band"]] = bands.get(r["band"], 0) + 1

    present = {(r["system"], r["name"]) for r in records}
    incidents = [
        next(r for r in records if (r["system"], r["name"]) == key)
        for key in INCIDENTS
        if key in present
    ]

    html = Template(TEMPLATE).render(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        model_version=cfg.model_version,
        total=len(records),
        bands=bands,
        top=records[:50],
        incidents=incidents,
    )
    path = Path(out)
    path.write_text(html, encoding="utf-8")
    return path, len(records)
