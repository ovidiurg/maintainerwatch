from __future__ import annotations

import json

from mw import lookup
from mw.config import load_config

INDEX = {
    "model_version": "0.5.3",
    "generated_at": "2026-11-23T15:21:22+00:00",
    "counts": {"packages": 1},
    "packages": {
        "npm:lodash": {
            "system": "npm",
            "name": "lodash",
            "score": 29.2,
            "band": "medium",
            "confidence": "evidence-only",
            "coverage": 0.92,
            "risk_type": "Maintainer concentration",
            "top_signals": [{"name": "bus_factor", "value": 0.89}],
        }
    },
}


def test_find_package_is_case_insensitive():
    assert lookup.find_package(INDEX, "npm", "LODASH")["name"] == "lodash"
    assert lookup.find_package(INDEX, "pypi", "lodash") is None


def test_format_text_includes_band_and_signal():
    result = {
        "found": True,
        **INDEX["packages"]["npm:lodash"],
        "model_version": INDEX["model_version"],
        "generated_at": INDEX["generated_at"],
    }
    text = lookup.format_text(result)
    assert "npm/lodash" in text
    assert "band: medium" in text
    assert "bus factor 0.89" in text
    assert "not a live verdict" in text


def test_lookup_reads_local_index(tmp_path):
    cfg = load_config()
    cfg.data_dir = tmp_path
    path = tmp_path / "index.json"
    path.write_text(json.dumps(INDEX), encoding="utf-8")
    result = lookup.lookup(cfg, "npm", "lodash", str(path))
    assert result["found"] is True
    assert result["score"] == 29.2
    assert result["top_signals"] == [{"name": "bus_factor", "value": 0.89}]
