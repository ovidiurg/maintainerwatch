from __future__ import annotations

import json

from mw.team_report import build_report, collect_manifests, render_html


def _index(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps({
        "model_version": "0.5.3",
        "generated_at": "2026-11-24T00:00:00+00:00",
        "packages": {
            "npm:pkg": {
                "system": "npm", "name": "pkg", "score": 62.0, "band": "high",
                "confidence": "high", "risk_type": "Maintainer takeover",
                "top_signals": [{"name": "publisher_change", "value": 1.0}],
            }
        },
    }), encoding="utf-8")
    return path


def test_collect_and_render_team_report(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "package.json").write_text('{"dependencies": {"pkg": "1.2.3"}}', encoding="utf-8")
    index = _index(tmp_path)
    packages = collect_manifests(root)
    assert packages[0]["name"] == "pkg"
    report = build_report(root, index)
    assert len(report["findings"]) == 1
    assert report["unknown"] == []
    html = render_html(report)
    assert "MaintainerWatch team report" in html
    assert "npm/pkg" in html
    assert "publisher_change" in html
