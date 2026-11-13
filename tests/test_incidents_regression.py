from __future__ import annotations

from pathlib import Path

import pytest

from mw import db
from mw.config import load_config
from mw.evaluate import replay

DB = Path(__file__).resolve().parents[1] / "data" / "maintainerwatch.sqlite"


@pytest.mark.skipif(not DB.exists(), reason="main DB not built")
def test_takeover_replay_regression():
    cfg = load_config()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    if conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0] == 0:
        conn.close()
        pytest.skip("no commit data in the local database")

    cases = [
        ("npm", "event-stream", "2018-11-20T00:00:00+00:00", 40.0),
        ("npm", "ua-parser-js", "2021-10-21T00:00:00+00:00", 20.0),
        ("github", "tukaani-project/xz", "2024-02-23T00:00:00+00:00", 30.0),
    ]
    for system, name, cutoff, minimum in cases:
        result = replay(conn, cfg, system, name, cutoff)
        assert result is not None, name
        assert result.score >= minimum, (name, result.score)
    conn.close()
