from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from . import db
from .config import Config

INCIDENTS = [
    ("npm", "event-stream"),
    ("npm", "ua-parser-js"),
    ("npm", "colors"),
    ("npm", "node-ipc"),
    ("pypi", "ctx"),
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
  <tr><th>System</th><th>Package</th><th>Score</th><th>Band</th><th>Downloads/wk</th><th>OSV</th><th>Repo</th></tr>
  {% for r in top %}
  <tr>
    <td>{{ r.system }}</td>
    <td>{{ r.name }}</td>
    <td>{{ r.score }}</td>
    <td class="{{ r.band }}">{{ r.band }}</td>
    <td>{{ r.downloads_weekly or 0 }}</td>
    <td>{{ r.osv_count or 0 }}</td>
    <td>{% if r.repo_url %}<a href="{{ r.repo_url }}">source</a>{% endif %}</td>
  </tr>
  {% endfor %}
</table>

<h2>Historical incidents</h2>
<p class="muted">Replay check: packages involved in past takeover incidents, if present in this dataset.</p>
<table>
  <tr><th>System</th><th>Package</th><th>Score</th><th>Band</th></tr>
  {% for r in incidents %}
  <tr><td>{{ r.system }}</td><td>{{ r.name }}</td><td>{{ r.score }}</td><td class="{{ r.band }}">{{ r.band }}</td></tr>
  {% else %}
  <tr><td colspan="4" class="muted">No incident packages ingested yet.</td></tr>
  {% endfor %}
</table>

<h2>Method</h2>
<p>Score = 100 × Σ(weight × value) / Σ(weight) over applicable signals:
publisher_change (30), bus_factor (20), account_age (15), release_anomaly (15),
signing_gap (10), typosquat (10). Bands: &lt;25 low, &lt;50 medium, else high.
Identity-gated signals only use links with high/medium confidence.</p>
<p class="muted">Only public, role-related data is used. See docs/gdpr.md.</p>
</body>
</html>
"""


def build_report(cfg: Config, out: str | Path = "report.html") -> tuple[Path, int]:
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    rows = conn.execute(
        """SELECT s.system, s.name, s.score, s.band,
                  p.downloads_weekly, p.osv_count, p.repo_url
           FROM scores s
           LEFT JOIN packages p ON p.system = s.system AND p.name = s.name
           ORDER BY s.score DESC, s.name ASC"""
    ).fetchall()
    conn.close()

    records = [dict(r) for r in rows]
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
