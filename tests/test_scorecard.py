from __future__ import annotations

import json

from mw import db
from mw.ingest.scorecard import fetch_scorecard


class FakeClient:
    def get_json(self, url):
        return {
            "score": 7.5,
            "checks": [{"name": "Dangerous-Workflow", "score": 0}],
        }


def test_fetch_scorecard_keeps_checks():
    score, checks = fetch_scorecard(FakeClient(), "https://github.com/o/r")
    assert score == 7.5
    assert json.loads(checks)[0]["name"] == "Dangerous-Workflow"


def test_update_repo_scorecard():
    conn = db.connect(":memory:")
    db.init_db(conn)
    conn.execute(
        "INSERT INTO repo_stats (system, name, repo_url) "
        "VALUES ('npm', 'pkg', 'https://github.com/o/r')"
    )
    db.update_repo_scorecard(conn, "npm", "pkg", 7.5, '[{"name":"Maintained","score":10}]')
    row = conn.execute("SELECT * FROM repo_stats WHERE name='pkg'").fetchone()
    assert row["scorecard_score"] == 7.5
    assert "Maintained" in row["scorecard_checks_json"]
    conn.close()


def test_enrich_scorecard_pipeline(tmp_path, monkeypatch):
    from mw import pipeline
    from mw.config import load_config

    cfg = load_config()
    cfg.db_path = tmp_path / "scorecard.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    conn.execute(
        "INSERT INTO repo_stats (system, name, repo_url) "
        "VALUES ('npm', 'pkg', 'https://github.com/o/r')"
    )
    conn.commit()
    conn.close()

    class Client:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(pipeline, "make_client", lambda cfg: Client())
    monkeypatch.setattr(
        pipeline, "fetch_scorecard",
        lambda client, repo_url: (7.5, '[{"name":"Maintained","score":10}]'),
    )
    result = pipeline.enrich_scorecard(cfg, limit=10)
    assert result == {"requested": 1, "updated": 1}
