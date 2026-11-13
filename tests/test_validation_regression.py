from __future__ import annotations

from pathlib import Path

import pytest

from mw import db, validation
from mw.config import load_config

DB = Path(__file__).resolve().parents[1] / "data" / "validation" / "maintainerwatch.sqlite"


@pytest.mark.skipif(not DB.exists(), reason="validation DB not built")
def test_validation_model_meets_baseline():
    cfg = load_config("config/validation.yaml")
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    result = validation.evaluate(conn, cfg, write_report=False)
    conn.close()

    assert result["coverage"]["positives_in_db"] >= 50
    assert result["metrics"]["auc"] >= 0.75
    assert result["metrics"]["precision_at_25"] >= 0.8
    threshold_40 = next(
        row for row in result["metrics"]["thresholds"] if row["threshold"] == 40.0
    )
    assert threshold_40["false_positive_rate"] <= 0.15
    assert threshold_40["recall"] >= 0.5
