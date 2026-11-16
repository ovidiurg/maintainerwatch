from __future__ import annotations

import json

from mw import pipeline
from mw.config import load_config


def test_run_all_is_best_effort_and_writes_summary(tmp_path, monkeypatch):
    cfg = load_config()
    cfg.data_dir = tmp_path
    cfg.db_path = tmp_path / "main.sqlite"
    cfg.ecosystems = ["npm"]
    calls = []

    monkeypatch.setattr(
        pipeline, "ingest_system",
        lambda cfg, system, top_n=None, with_github=False: calls.append(f"ingest:{system}") or {"packages": 2},
    )
    monkeypatch.setattr(
        pipeline, "enrich_impact", lambda cfg, limit=500: {"updated": 1},
    )
    monkeypatch.setattr(
        pipeline, "enrich_findings", lambda cfg, limit=500: {"updated": 1},
    )
    monkeypatch.setattr(
        pipeline, "enrich_scorecard", lambda cfg, limit=500: {"updated": 1},
    )
    monkeypatch.setattr(
        pipeline, "backfill_osv", lambda cfg, limit=500, malicious_only=False: {"updated": 1},
    )
    monkeypatch.setattr(
        pipeline, "maintain",
        lambda cfg, with_commits=True, export=True: {"scores": {"scored": 2}},
    )

    result = pipeline.run_all(cfg, top_n=2, enrich=True, export=True)
    assert result["ok"] is True
    assert result["outputs"]["index"].endswith("maintainerwatch-index.json")
    assert calls == ["ingest:npm"]
    summary = json.loads((tmp_path / "main-summary.json").read_text())
    assert summary["steps"]["ingest:npm"]["ok"] is True
    assert summary["steps"]["enrich:impact"]["ok"] is True
    assert summary["steps"]["maintain"]["ok"] is True


def test_run_all_records_failure_and_continues(tmp_path, monkeypatch):
    cfg = load_config()
    cfg.data_dir = tmp_path
    cfg.db_path = tmp_path / "main.sqlite"
    cfg.ecosystems = ["npm"]

    def fail(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "ingest_system", fail)
    monkeypatch.setattr(pipeline, "maintain", lambda **kwargs: {"scores": {"scored": 0}})
    result = pipeline.run_all(cfg, top_n=1, enrich=False, build_index=False)
    assert result["ok"] is False
    assert "network down" in result["errors"][0]
    assert json.loads((tmp_path / "main-summary.json").read_text())["ok"] is False
